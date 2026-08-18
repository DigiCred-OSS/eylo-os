"""Durable AgentRun workflow boundary over Absurd task contexts."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, TypeVar
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability
from eylo.modules.agent_runs.budgets import (
    activate_agent_run_reservation_in_transaction,
    agent_run_execution_budget_scope,
    check_agent_run_active_time,
    release_agent_run_reservation_in_transaction,
)
from eylo.modules.agent_runs.domain import (
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
    ExecutionBudgetExceeded,
    ExecutionUsageNotReported,
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
)
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.agent_runs.repositories import AgentRunRepository
from eylo.modules.agents.models import AgentRevisionModel, AgentsModel
from eylo.modules.auth.models import ApiKeyModel, AuthSessionModel
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.members.models import MemberModel, MemberStatus
from eylo.modules.user_sessions.events import file_user_session_fact

_STEP_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_EVENT_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}$")
_TERMINAL_LIFECYCLES = {
    AgentRunLifecycle.COMPLETED,
    AgentRunLifecycle.FAILED,
    AgentRunLifecycle.CANCELLED,
}

T = TypeVar("T")


class AgentRunClaimNotFound(Exception):
    """An engine task references no current organization-owned AgentRun."""


class AgentRunBindingPending(Exception):
    """Spawn committed before the product task binding became visible."""


class AgentRunExecutionUnavailable(Exception):
    """The registered workflow has no product executor yet."""


class AgentRunExecutionIncomplete(Exception):
    """An executor returned without committing a terminal product state."""


@dataclass(frozen=True, slots=True)
class AgentRunExecutionClaim:
    """Current product authority reloaded from IDs when Absurd claims work."""

    organization_id: UUID
    run_id: UUID
    principal: InitiatingPrincipalRef
    agent_id: UUID
    agent_revision: int
    agent_revision_id: UUID
    origin_kind: AgentRunOriginKind
    origin_message_id: UUID | None
    origin_schedule_run_id: UUID | None
    session_context_digest: str
    context_manifest: dict[str, Any]
    goal: str


@dataclass(frozen=True, slots=True)
class AgentRunWorkflowReceipt:
    """Bounded engine result; canonical output stays on Eylo product rows."""

    organization_id: UUID
    run_id: UUID
    lifecycle: AgentRunLifecycle
    outcome: AgentRunOutcome

    def as_json(self) -> dict[str, str]:
        return {
            "organization_id": str(self.organization_id),
            "run_id": str(self.run_id),
            "lifecycle": self.lifecycle.value,
            "outcome": self.outcome.value,
        }


class AgentRunWorkflowContext:
    """Small versioned checkpoint API exposed to the product executor."""

    def __init__(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        task_context: AsyncTaskContext,
    ):
        self._organization_id = organization_id
        self._run_id = run_id
        self._task_context = task_context

    async def heartbeat(self, *, seconds: int) -> int:
        if seconds < 1:
            raise ValueError("Heartbeat duration must be positive.")
        remaining_milliseconds = await check_agent_run_active_time(
            organization_id=self._organization_id,
            run_id=self._run_id,
        )
        await self._task_context.heartbeat(seconds=seconds)
        return remaining_milliseconds

    async def step(
        self,
        *,
        key: str,
        version: int,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        return await self._task_context.step(
            self.step_identity(key=key, version=version),
            operation,
        )

    async def await_event(
        self,
        *,
        event_name: str,
        key: str,
        version: int,
    ) -> Any:
        if not _EVENT_NAME.fullmatch(event_name):
            raise ValueError("Event name is invalid.")
        return await self._task_context.await_event(
            event_name,
            step_name=self.step_identity(key=key, version=version),
            timeout=None,
        )

    def step_identity(self, *, key: str, version: int) -> str:
        if not _STEP_KEY.fullmatch(key):
            raise ValueError("Step key is invalid.")
        if version < 1:
            raise ValueError("Step version must be positive.")
        return f"agent-run:{self._run_id}:{key}:v{version}"


class AgentRunExecutor(Protocol):
    """Product execution seam implemented by the conversation loop in F-006."""

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None: ...


class AgentRunComputeCleanup(Protocol):
    """Pipeline-owned cleanup injected at the workflow composition boundary."""

    async def __call__(
        self,
        *,
        organization_id: UUID,
        agent_run_id: UUID,
    ) -> None: ...


class AgentRunFailureHandler(Protocol):
    """Application callback that owns terminal projections outside AgentRun."""

    async def __call__(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        failure_summary: str,
    ) -> None: ...


class UnwiredAgentRunExecutor:
    """Fail visibly until F-006 connects the neutral agent loop."""

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        del claim, context
        raise AgentRunExecutionUnavailable("AgentRun executor is not wired.")


class AgentRunExecutorRouter:
    """Dispatch one claimed run by its immutable origin kind."""

    def __init__(self, executors: Mapping[AgentRunOriginKind, AgentRunExecutor]):
        self._executors = dict(executors)

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        executor = self._executors.get(claim.origin_kind)
        if executor is None:
            raise AgentRunExecutionUnavailable(
                f"No executor is registered for {claim.origin_kind.value} AgentRuns."
            )
        await executor.execute(claim, context)


class AgentRunWorkflow:
    """Reload product authority, then delegate execution without duplicating claims."""

    def __init__(
        self,
        executor: AgentRunExecutor,
        *,
        compute_cleanup: AgentRunComputeCleanup | None = None,
        failure_handler: AgentRunFailureHandler | None = None,
    ):
        self._executor = executor
        self._compute_cleanup = compute_cleanup
        self._failure_handler = failure_handler

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, str]:
        organization_id, run_id = _parse_task_params(params)
        try:
            await task_context.heartbeat(seconds=120)
            claim = await _claim_run(
                organization_id=organization_id,
                run_id=run_id,
            )
            if isinstance(claim, AgentRunWorkflowReceipt):
                await self._cleanup_compute(
                    organization_id=organization_id,
                    run_id=run_id,
                )
                return claim.as_json()

            context = AgentRunWorkflowContext(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                task_context=task_context,
            )
            with agent_run_execution_budget_scope(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            ):
                await self._executor.execute(claim, context)
            await self._cleanup_compute(
                organization_id=organization_id,
                run_id=run_id,
            )
            receipt = await _load_terminal_receipt(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            )
            return receipt.as_json()
        except (ExecutionBudgetExceeded, ExecutionUsageNotReported) as error:
            await self._cleanup_compute(
                organization_id=organization_id,
                run_id=run_id,
            )
            await self._fail_run(
                organization_id=organization_id,
                run_id=run_id,
                failure_summary=str(error),
            )
            receipt = await _load_terminal_receipt(
                organization_id=organization_id,
                run_id=run_id,
            )
            return receipt.as_json()
        except CancelledTask:
            from eylo.modules.agent_runs.service import (
                accept_agent_run_cancellation,
            )

            await self._cleanup_compute(
                organization_id=organization_id,
                run_id=run_id,
            )
            await accept_agent_run_cancellation(
                organization_id=organization_id,
                run_id=run_id,
            )
            raise
        except BaseException:
            await self._cleanup_compute(
                organization_id=organization_id,
                run_id=run_id,
            )
            if await _cancellation_was_requested(
                organization_id=organization_id,
                run_id=run_id,
            ):
                from eylo.modules.agent_runs.service import (
                    accept_agent_run_cancellation,
                )

                await accept_agent_run_cancellation(
                    organization_id=organization_id,
                    run_id=run_id,
                )
            raise

    async def _fail_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        failure_summary: str,
    ) -> None:
        if self._failure_handler is not None:
            await self._failure_handler(
                organization_id=organization_id,
                run_id=run_id,
                failure_summary=failure_summary,
            )
            return

        from eylo.modules.agent_runs.service import fail_agent_run

        await fail_agent_run(
            organization_id=organization_id,
            run_id=run_id,
            failure_summary=failure_summary,
        )

    async def _cleanup_compute(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> None:
        if self._compute_cleanup is None:
            return
        await self._compute_cleanup(
            organization_id=organization_id,
            agent_run_id=run_id,
        )


def _parse_task_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "run_id"}:
        raise ValueError("AgentRun task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["run_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError("AgentRun task params contain an invalid UUID.") from error


async def _cancellation_was_requested(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> bool:
    async with start_transaction(ro=True) as session:
        return bool(
            await session.scalar(
                select(AgentRunModel.cancellation_requested_at).where(
                    AgentRunModel.organization_id == organization_id,
                    AgentRunModel.id == run_id,
                    AgentRunModel.deleted.is_(False),
                )
            )
        )


async def _claim_run(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> AgentRunExecutionClaim | AgentRunWorkflowReceipt:
    async with start_transaction() as session:
        repository = AgentRunRepository(session)
        run = await repository.get(
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if run is None:
            raise AgentRunClaimNotFound
        if run.lifecycle in _TERMINAL_LIFECYCLES:
            return _receipt(run)
        if run.absurd_task_id is None:
            raise AgentRunBindingPending("AgentRun task binding is not visible yet.")
        if run.cancellation_requested_at is not None:
            receipt = _accept_cancellation(run)
            from eylo.modules.agent_runs.service import (
                cancel_pending_input_requests_in_transaction,
            )

            await cancel_pending_input_requests_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
                cancelled_at=run.cancelled_at,
            )
            await release_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )
            await _file_run_fact(
                session,
                run,
                event_type="agent.run.cancelled",
                payload={},
            )
            return receipt

        revision_id = await session.scalar(
            select(AgentRevisionModel.id).where(
                AgentRevisionModel.organization_id == organization_id,
                AgentRevisionModel.agent_id == run.agent_id,
                AgentRevisionModel.revision == run.agent_revision,
                AgentRevisionModel.availability == RevisionAvailability.PUBLISHED.value,
                AgentRevisionModel.deleted.is_(False),
            )
        )
        if revision_id is None:
            receipt = _refuse_run(
                run,
                "Pinned agent revision is no longer executable.",
            )
            await release_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )
            await _file_run_fact(
                session,
                run,
                event_type="agent.run.failed",
                payload={"reason": "agent_revision_unavailable"},
            )
            return receipt
        if not await _principal_is_current(session, run):
            receipt = _refuse_run(
                run,
                "Initiating authority is no longer active.",
            )
            await release_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )
            await _file_run_fact(
                session,
                run,
                event_type="agent.run.failed",
                payload={"reason": "principal_inactive"},
            )
            return receipt

        if run.lifecycle is AgentRunLifecycle.QUEUED:
            await activate_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )
            run.lifecycle = AgentRunLifecycle.RUNNING
            run.started_at = datetime.now(timezone.utc)
            run.state_revision += 1
            await session.flush()
            await _file_run_fact(
                session,
                run,
                event_type="agent.run.started",
                payload={},
            )
        elif run.lifecycle is AgentRunLifecycle.RUNNING:
            await activate_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )

        return AgentRunExecutionClaim(
            organization_id=run.organization_id,
            run_id=run.id,
            principal=InitiatingPrincipalRef(
                organization_id=run.organization_id,
                kind=run.initiating_principal_kind,
                principal_id=run.initiating_principal_id,
            ),
            agent_id=run.agent_id,
            agent_revision=run.agent_revision,
            agent_revision_id=revision_id,
            origin_kind=run.origin_kind,
            origin_message_id=run.origin_message_id,
            origin_schedule_run_id=run.origin_schedule_run_id,
            session_context_digest=run.session_context_digest,
            context_manifest=deepcopy(run.context_manifest),
            goal=run.goal,
        )


async def _principal_is_current(session: AsyncSession, run: AgentRunModel) -> bool:
    common = (
        run.organization_id,
        run.initiating_principal_id,
    )
    principal_query = {
        InitiatingPrincipalKind.MEMBER: select(MemberModel.id).where(
            MemberModel.organization_id == common[0],
            MemberModel.id == common[1],
            MemberModel.status == MemberStatus.ACTIVE,
            MemberModel.deleted.is_(False),
        ),
        InitiatingPrincipalKind.CONTACT: select(ContactsModel.id).where(
            ContactsModel.organization_id == common[0],
            ContactsModel.id == common[1],
            ContactsModel.deleted.is_(False),
        ),
        InitiatingPrincipalKind.API_KEY: select(ApiKeyModel.id).where(
            ApiKeyModel.organization_id == common[0],
            ApiKeyModel.id == common[1],
            ApiKeyModel.is_active.is_(True),
            ApiKeyModel.deleted.is_(False),
            or_(ApiKeyModel.expires_at.is_(None), ApiKeyModel.expires_at > func.now()),
        ),
        InitiatingPrincipalKind.WIDGET: select(AuthSessionModel.id)
        .join(
            ContactsModel,
            and_(
                ContactsModel.id == AuthSessionModel.contact_id,
                ContactsModel.organization_id == AuthSessionModel.organization_id,
            ),
        )
        .where(
            AuthSessionModel.organization_id == common[0],
            AuthSessionModel.id == common[1],
            AuthSessionModel.expires_at > func.now(),
            AuthSessionModel.deleted.is_(False),
            ContactsModel.deleted.is_(False),
        ),
        InitiatingPrincipalKind.WORKER: select(AgentsModel.id).where(
            AgentsModel.organization_id == common[0],
            AgentsModel.id == common[1],
            AgentsModel.lifecycle == DefinitionLifecycle.PUBLISHED.value,
            AgentsModel.deleted.is_(False),
        ),
    }[run.initiating_principal_kind]
    return await session.scalar(principal_query) is not None


def _refuse_run(run: AgentRunModel, summary: str) -> AgentRunWorkflowReceipt:
    now = datetime.now(timezone.utc)
    run.lifecycle = AgentRunLifecycle.FAILED
    run.outcome = AgentRunOutcome.FAILED
    run.failure_summary = summary
    run.finished_at = now
    run.state_revision += 1
    return _receipt(run)


def _accept_cancellation(run: AgentRunModel) -> AgentRunWorkflowReceipt:
    now = datetime.now(timezone.utc)
    run.lifecycle = AgentRunLifecycle.CANCELLED
    run.outcome = AgentRunOutcome.CANCELLED
    run.cancelled_at = now
    run.finished_at = now
    run.state_revision += 1
    return _receipt(run)


async def _file_run_fact(
    session: AsyncSession,
    run: AgentRunModel,
    *,
    event_type: str,
    payload: dict,
) -> None:
    if run.user_session_id is None:
        return
    await file_user_session_fact(
        session,
        organization_id=run.organization_id,
        user_session_id=run.user_session_id,
        subject_type="agent.run",
        subject_id=run.id,
        event_type=event_type,
        payload={
            "agent_id": str(run.agent_id),
            "agent_revision": run.agent_revision,
            **payload,
        },
    )


async def _load_terminal_receipt(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> AgentRunWorkflowReceipt:
    async with start_transaction(ro=True) as session:
        run = await AgentRunRepository(session).get(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            raise AgentRunClaimNotFound
        if run.lifecycle not in _TERMINAL_LIFECYCLES:
            raise AgentRunExecutionIncomplete(
                "AgentRun executor returned before committing a terminal state."
            )
        return _receipt(run)


def _receipt(run: AgentRunModel) -> AgentRunWorkflowReceipt:
    if run.lifecycle not in _TERMINAL_LIFECYCLES or run.outcome is None:
        raise AgentRunExecutionIncomplete("AgentRun has no terminal product result.")
    return AgentRunWorkflowReceipt(
        organization_id=run.organization_id,
        run_id=run.id,
        lifecycle=run.lifecycle,
        outcome=run.outcome,
    )


__all__ = [
    "AgentRunBindingPending",
    "AgentRunExecutionClaim",
    "AgentRunExecutionIncomplete",
    "AgentRunExecutionUnavailable",
    "AgentRunExecutor",
    "AgentRunExecutorRouter",
    "AgentRunWorkflow",
    "AgentRunWorkflowContext",
    "AgentRunWorkflowReceipt",
    "UnwiredAgentRunExecutor",
]
