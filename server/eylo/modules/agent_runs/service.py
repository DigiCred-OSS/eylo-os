"""Application commands and queries for organization-owned agent runs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic_core import to_jsonable_python
from referencing.jsonschema import DRAFT202012
from sqlalchemy import JSON, update
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.budgets import (
    activate_agent_run_reservation_in_transaction,
    release_agent_run_reservation_in_transaction,
    reserve_agent_run_in_transaction,
)
from eylo.modules.agent_runs.domain import (
    AgentInputRequestKind,
    AgentInputRequestStatus,
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
    ExecutionBudgetExceeded,
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
    validate_lifecycle_outcome,
)
from eylo.modules.agent_runs.models import (
    AgentInputRequestModel,
    AgentRunModel,
    AgentRunStepModel,
    OrganizationExecutionReservationModel,
)
from eylo.modules.agent_runs.repositories import AgentRunRepository
from eylo.modules.agent_runs.schemas import (
    AgentInputRequestRead,
    AgentInputResponseRequest,
    AgentRunCancellationDisposition,
    AgentRunCancellationRead,
    AgentRunRead,
    AgentRunReservationRead,
    AgentRunStepRead,
)
from eylo.modules.user_sessions.events import file_user_session_fact


class AgentRunNotFound(Exception):
    """The run is missing or outside the caller's organization."""


class AgentInputRequestNotFound(Exception):
    """The input request is missing or outside the caller's organization."""


class AgentRunConflict(Exception):
    """A command no longer matches the durable run state it observed."""


_MAX_INPUT_SCHEMA_BYTES = 32_768
_MAX_INPUT_RESPONSE_BYTES = 65_536
_MAX_INPUT_SCHEMA_DEPTH = 32
_MAX_INPUT_SCHEMA_NODES = 1_024


@dataclass(frozen=True, slots=True)
class ScheduleAgentRunFiling:
    """Atomic schedule-occurrence filing result."""

    run_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class ObjectiveAgentRunFiling:
    """Idempotent direct-objective filing result."""

    run_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class AgentRunWaitState:
    """Internal resume state; engine events carry only these product IDs."""

    request_id: UUID
    kind: AgentInputRequestKind
    status: AgentInputRequestStatus
    event_name: str
    resume_step_key: str
    response: object
    continuation: dict


async def file_schedule_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    schedule_run_id: UUID,
    principal: InitiatingPrincipalRef,
    agent_id: UUID,
    agent_revision: int,
    goal: str,
    context_manifest: dict,
) -> ScheduleAgentRunFiling:
    """File one run for one immutable occurrence in the caller's transaction."""
    if principal.organization_id != organization_id:
        raise AgentRunConflict("Schedule principal belongs to another organization.")
    if principal.kind not in {
        InitiatingPrincipalKind.MEMBER,
        InitiatingPrincipalKind.WORKER,
    }:
        raise AgentRunConflict("A schedule must be initiated by a member or agent.")
    goal = goal.strip()
    if not goal or len(goal) > 16384:
        raise AgentRunConflict(
            "Schedule AgentRun goal must contain 1-16384 characters."
        )
    if agent_revision < 1:
        raise AgentRunConflict("Schedule AgentRun requires a positive agent revision.")

    normalized_context = to_jsonable_python(context_manifest)
    if not isinstance(normalized_context, dict):
        raise AgentRunConflict("Schedule AgentRun context manifest must be an object.")
    encoded_context = json.dumps(
        normalized_context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded_context) > 16384:
        raise AgentRunConflict(
            "Schedule AgentRun context manifest exceeds 16384 encoded bytes."
        )
    context_digest = hashlib.sha256(encoded_context).hexdigest()
    idempotency_key = f"schedule:{organization_id}:{schedule_run_id}"

    repository = AgentRunRepository(session)
    await repository.acquire_filing_lock(idempotency_key)
    existing = await repository.get_by_idempotency_key(
        organization_id=organization_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if not _same_schedule_filing(
            existing,
            schedule_run_id=schedule_run_id,
            principal=principal,
            agent_id=agent_id,
            agent_revision=agent_revision,
            goal=goal,
            context_manifest=normalized_context,
            context_digest=context_digest,
        ):
            raise AgentRunConflict(
                "Schedule occurrence was already filed with different semantics."
            )
        return ScheduleAgentRunFiling(run_id=existing.id, created=False)

    run = AgentRunModel(
        id=uuid4(),
        organization_id=organization_id,
        initiating_principal_kind=principal.kind,
        initiating_principal_id=principal.principal_id,
        agent_id=agent_id,
        agent_revision=agent_revision,
        origin_kind=AgentRunOriginKind.SCHEDULE_OCCURRENCE,
        origin_schedule_run_id=schedule_run_id,
        session_context_digest=context_digest,
        context_manifest=normalized_context,
        idempotency_key=idempotency_key,
        goal=goal,
    )
    session.add(run)
    await session.flush()
    await reserve_agent_run_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run.id,
    )
    return ScheduleAgentRunFiling(run_id=run.id, created=True)


async def file_objective_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    principal: InitiatingPrincipalRef,
    agent_id: UUID,
    agent_revision: int,
    goal: str,
    context_manifest: dict,
    idempotency_token: str,
) -> ObjectiveAgentRunFiling:
    """File one member-requested objective without a second durable resource."""
    if principal.organization_id != organization_id:
        raise AgentRunConflict("Objective principal belongs to another organization.")
    if principal.kind is not InitiatingPrincipalKind.MEMBER:
        raise AgentRunConflict(
            "An objective must be initiated by an organization member."
        )
    goal = goal.strip()
    if not goal or len(goal) > 16384:
        raise AgentRunConflict("Objective goal must contain 1-16384 characters.")
    if agent_revision < 1:
        raise AgentRunConflict("Objective AgentRun requires a positive agent revision.")

    token = idempotency_token.strip()
    if not token or len(token) > 240:
        raise AgentRunConflict("Idempotency-Key must contain 1-240 characters.")
    normalized_context, context_digest = _normalize_context_manifest(
        context_manifest,
        label="Objective",
    )
    idempotency_key = f"objective:{organization_id}:{token}"

    repository = AgentRunRepository(session)
    await repository.acquire_filing_lock(idempotency_key)
    existing = await repository.get_by_idempotency_key(
        organization_id=organization_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if not _same_objective_filing(
            existing,
            principal=principal,
            agent_id=agent_id,
            agent_revision=agent_revision,
            goal=goal,
            context_manifest=normalized_context,
            context_digest=context_digest,
        ):
            raise AgentRunConflict(
                "Idempotency-Key was already used for a different objective."
            )
        return ObjectiveAgentRunFiling(run_id=existing.id, created=False)

    run = AgentRunModel(
        id=uuid4(),
        organization_id=organization_id,
        initiating_principal_kind=principal.kind,
        initiating_principal_id=principal.principal_id,
        agent_id=agent_id,
        agent_revision=agent_revision,
        origin_kind=AgentRunOriginKind.OBJECTIVE,
        session_context_digest=context_digest,
        context_manifest=normalized_context,
        idempotency_key=idempotency_key,
        goal=goal,
    )
    session.add(run)
    await session.flush()
    await reserve_agent_run_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run.id,
    )
    return ObjectiveAgentRunFiling(run_id=run.id, created=True)


def _normalize_context_manifest(
    context_manifest: dict, *, label: str
) -> tuple[dict, str]:
    normalized = to_jsonable_python(context_manifest)
    if not isinstance(normalized, dict):
        raise AgentRunConflict(f"{label} AgentRun context manifest must be an object.")
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > 16384:
        raise AgentRunConflict(
            f"{label} AgentRun context manifest exceeds 16384 encoded bytes."
        )
    return normalized, hashlib.sha256(encoded).hexdigest()


def _same_schedule_filing(
    run: AgentRunModel,
    *,
    schedule_run_id: UUID,
    principal: InitiatingPrincipalRef,
    agent_id: UUID,
    agent_revision: int,
    goal: str,
    context_manifest: dict,
    context_digest: str,
) -> bool:
    return (
        run.origin_kind is AgentRunOriginKind.SCHEDULE_OCCURRENCE
        and run.origin_schedule_run_id == schedule_run_id
        and run.origin_message_id is None
        and run.initiating_principal_kind is principal.kind
        and run.initiating_principal_id == principal.principal_id
        and run.agent_id == agent_id
        and run.agent_revision == agent_revision
        and run.goal == goal
        and run.context_manifest == context_manifest
        and run.session_context_digest == context_digest
    )


def _same_objective_filing(
    run: AgentRunModel,
    *,
    principal: InitiatingPrincipalRef,
    agent_id: UUID,
    agent_revision: int,
    goal: str,
    context_manifest: dict,
    context_digest: str,
) -> bool:
    return (
        run.origin_kind is AgentRunOriginKind.OBJECTIVE
        and run.origin_message_id is None
        and run.origin_schedule_run_id is None
        and run.initiating_principal_kind is principal.kind
        and run.initiating_principal_id == principal.principal_id
        and run.agent_id == agent_id
        and run.agent_revision == agent_revision
        and run.goal == goal
        and run.context_manifest == context_manifest
        and run.session_context_digest == context_digest
    )


async def pause_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    kind: AgentInputRequestKind,
    prompt: str,
    expected_response_schema: dict,
    continuation: dict,
) -> AgentInputRequestModel:
    """Persist one identified indefinite wait with the run and pause message."""
    prompt = prompt.strip()
    if not prompt or len(prompt) > 8192:
        raise ValueError("Agent input prompt must contain 1-8192 characters.")
    normalized_schema = _validated_response_schema(expected_response_schema)
    normalized_continuation = to_jsonable_python(continuation)
    if not isinstance(normalized_continuation, dict):
        raise ValueError("Agent input continuation must be an object.")

    run = await AgentRunRepository(session).get(
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if run is None:
        raise AgentRunNotFound
    if run.lifecycle is not AgentRunLifecycle.RUNNING:
        raise AgentRunConflict(
            f"A {run.lifecycle.value} AgentRun cannot start an input wait."
        )
    if run.cancellation_requested_at is not None:
        raise AgentRunConflict("A cancelling AgentRun cannot start an input wait.")

    request_id = uuid4()
    request = AgentInputRequestModel(
        id=request_id,
        organization_id=organization_id,
        run_id=run_id,
        kind=kind,
        prompt=prompt,
        expected_response_schema=normalized_schema,
        continuation=normalized_continuation,
        event_name=f"agent-run-input:{run_id}:{request_id}",
        resume_step_key=f"input:{request_id}",
    )
    session.add(request)
    run.lifecycle = {
        AgentInputRequestKind.INPUT: AgentRunLifecycle.WAITING_FOR_INPUT,
        AgentInputRequestKind.APPROVAL: AgentRunLifecycle.WAITING_FOR_APPROVAL,
    }[kind]
    run.waiting_at = datetime.now(timezone.utc)
    run.state_revision += 1
    exceeded = await release_agent_run_reservation_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)
    await session.flush()
    await _file_agent_run_fact(
        session,
        run,
        event_type=(
            "agent.run.waiting_for_input"
            if kind is AgentInputRequestKind.INPUT
            else "agent.run.waiting_for_approval"
        ),
        payload={"input_request_id": str(request.id)},
    )
    await _file_agent_run_fact(
        session,
        run,
        event_type="agent.input.requested",
        payload={
            "input_request_id": str(request.id),
            "request_kind": kind.value,
        },
        subject_type="agent.input",
        subject_id=request.id,
    )
    return request


async def load_agent_run_wait(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> AgentRunWaitState | None:
    """Load the latest request only while the product run is waiting."""
    async with start_transaction(ro=True) as session:
        repository = AgentRunRepository(session)
        run = await repository.get(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            raise AgentRunNotFound
        requests = await repository.list_input_requests(
            organization_id=organization_id,
            run_ids=[run_id],
        )
        if run.lifecycle is AgentRunLifecycle.RUNNING:
            if (
                not requests
                or requests[-1].status is not AgentInputRequestStatus.ANSWERED
            ):
                return None
        elif run.lifecycle not in {
            AgentRunLifecycle.WAITING_FOR_INPUT,
            AgentRunLifecycle.WAITING_FOR_APPROVAL,
        }:
            return None
        elif not requests:
            raise AgentRunConflict("Waiting AgentRun has no identified request.")
        request = requests[-1]
        expected_lifecycle = {
            AgentInputRequestKind.INPUT: AgentRunLifecycle.WAITING_FOR_INPUT,
            AgentInputRequestKind.APPROVAL: AgentRunLifecycle.WAITING_FOR_APPROVAL,
        }[request.kind]
        if request.status not in {
            AgentInputRequestStatus.PENDING,
            AgentInputRequestStatus.ANSWERED,
        } or run.lifecycle not in {
            expected_lifecycle,
            AgentRunLifecycle.RUNNING,
        }:
            raise AgentRunConflict("AgentRun wait state is internally inconsistent.")
        return AgentRunWaitState(
            request_id=request.id,
            kind=request.kind,
            status=request.status,
            event_name=request.event_name,
            resume_step_key=request.resume_step_key,
            response=request.response,
            continuation=dict(request.continuation),
        )


async def resume_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    request_id: UUID,
) -> AgentRunWaitState:
    """Move an answered wait back to running in the resume transaction."""
    repository = AgentRunRepository(session)
    run = await repository.get(
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if run is None:
        raise AgentRunNotFound
    request = await repository.get_input_request(
        organization_id=organization_id,
        run_id=run_id,
        request_id=request_id,
        for_update=True,
    )
    if request is None:
        raise AgentInputRequestNotFound
    if request.status is not AgentInputRequestStatus.ANSWERED:
        raise AgentRunConflict("AgentRun input request has not been answered.")
    if run.cancellation_requested_at is not None:
        raise AgentRunConflict("A cancelling AgentRun cannot resume.")
    if run.lifecycle is not AgentRunLifecycle.RUNNING:
        _require_answerable_lifecycle(run, request)
        await activate_agent_run_reservation_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
        )
        run.lifecycle = AgentRunLifecycle.RUNNING
        run.waiting_at = None
        run.state_revision += 1
        await session.flush()
        await _file_agent_run_fact(
            session,
            run,
            event_type="agent.run.resumed",
            payload={"input_request_id": str(request.id)},
        )
    return AgentRunWaitState(
        request_id=request.id,
        kind=request.kind,
        status=request.status,
        event_name=request.event_name,
        resume_step_key=request.resume_step_key,
        response=request.response,
        continuation=dict(request.continuation),
    )


async def finish_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    lifecycle: AgentRunLifecycle,
    outcome: AgentRunOutcome,
    result: dict | None = None,
    outcome_reason: str | None = None,
    failure_summary: str | None = None,
) -> None:
    """Commit one terminal product result in the caller's output transaction."""
    validate_lifecycle_outcome(lifecycle, outcome)
    if lifecycle is AgentRunLifecycle.COMPLETED:
        if result is None or failure_summary is not None:
            raise ValueError("Completed AgentRun requires a result and no failure.")
    elif lifecycle is AgentRunLifecycle.FAILED:
        if result is not None or not failure_summary or not failure_summary.strip():
            raise ValueError("Failed AgentRun requires a non-empty failure summary.")
    else:
        raise ValueError("Conversation execution can finish only completed or failed.")
    if failure_summary is not None and len(failure_summary) > 2000:
        raise ValueError("AgentRun failure summary exceeds 2000 characters.")
    if outcome_reason is not None and len(outcome_reason) > 4000:
        raise ValueError("AgentRun outcome reason exceeds 4000 characters.")

    run = await AgentRunRepository(session).get(
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if run is None:
        raise AgentRunNotFound
    if run.lifecycle is not AgentRunLifecycle.RUNNING:
        raise AgentRunConflict(
            f"A {run.lifecycle.value} AgentRun cannot accept an execution result."
        )
    if run.cancellation_requested_at is not None:
        raise AgentRunConflict("A cancelling AgentRun cannot accept a result.")

    run.lifecycle = lifecycle
    run.outcome = outcome
    run.result = result
    run.outcome_reason = outcome_reason
    run.failure_summary = failure_summary
    run.finished_at = datetime.now(timezone.utc)
    run.state_revision += 1
    exceeded = await release_agent_run_reservation_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)
    await session.flush()
    await _file_agent_run_fact(
        session,
        run,
        event_type=f"agent.run.{lifecycle.value}",
        payload={"outcome": outcome.value},
    )


async def fail_agent_run(
    *,
    organization_id: UUID,
    run_id: UUID,
    failure_summary: str,
) -> None:
    """Record a deterministic execution refusal, including during a wait."""
    async with start_transaction() as session:
        await fail_agent_run_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
            failure_summary=failure_summary,
        )


async def fail_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    failure_summary: str,
) -> AgentRunModel:
    """Fail one run inside the caller's product-state transaction."""
    failure_summary = failure_summary.strip()
    if not failure_summary:
        raise ValueError("Failed AgentRun requires a non-empty failure summary.")
    if len(failure_summary) > 2000:
        raise ValueError("AgentRun failure summary exceeds 2000 characters.")

    run = await AgentRunRepository(session).get(
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if run is None:
        raise AgentRunNotFound
    if run.lifecycle is AgentRunLifecycle.FAILED:
        if run.failure_summary == failure_summary:
            return run
        raise AgentRunConflict("AgentRun already failed for a different reason.")
    if run.lifecycle not in {
        AgentRunLifecycle.QUEUED,
        AgentRunLifecycle.RUNNING,
        AgentRunLifecycle.WAITING_FOR_INPUT,
        AgentRunLifecycle.WAITING_FOR_APPROVAL,
    }:
        raise AgentRunConflict(
            f"A {run.lifecycle.value} AgentRun cannot accept an execution failure."
        )
    if run.cancellation_requested_at is not None:
        raise AgentRunConflict("A cancelling AgentRun cannot accept a failure.")

    await cancel_pending_input_requests_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    run.lifecycle = AgentRunLifecycle.FAILED
    run.outcome = AgentRunOutcome.FAILED
    run.result = None
    run.outcome_reason = None
    run.failure_summary = failure_summary
    run.waiting_at = None
    run.finished_at = datetime.now(timezone.utc)
    run.state_revision += 1
    await release_agent_run_reservation_in_transaction(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    await session.flush()
    await _file_agent_run_fact(
        session,
        run,
        event_type="agent.run.failed",
        payload={"outcome": AgentRunOutcome.FAILED.value},
    )
    return run


async def cancel_pending_input_requests_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    cancelled_at: datetime | None = None,
) -> None:
    """Close every still-pending identified request with its parent run."""
    now = cancelled_at or datetime.now(timezone.utc)
    await session.execute(
        update(AgentInputRequestModel)
        .where(
            AgentInputRequestModel.organization_id == organization_id,
            AgentInputRequestModel.run_id == run_id,
            AgentInputRequestModel.status == AgentInputRequestStatus.PENDING,
            AgentInputRequestModel.deleted.is_(False),
        )
        .values(
            status=AgentInputRequestStatus.CANCELLED,
            cancelled_at=now,
            state_revision=AgentInputRequestModel.state_revision + 1,
        )
    )


async def get_agent_run(*, organization_id: UUID, run_id: UUID) -> AgentRunRead:
    async with start_transaction(ro=True) as session:
        repository = AgentRunRepository(session)
        run = await repository.get(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            raise AgentRunNotFound
        return await _project_one(repository, run)


async def list_agent_runs(
    *,
    organization_id: UUID,
    limit: int,
    offset: int,
) -> list[AgentRunRead]:
    async with start_transaction(ro=True) as session:
        repository = AgentRunRepository(session)
        runs = await repository.list(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )
        return await _project_many(
            repository,
            runs,
            organization_id=organization_id,
        )


async def list_objective_agent_runs(
    *,
    organization_id: UUID,
    agent_id: UUID | None,
    lifecycle: AgentRunLifecycle | None,
    limit: int,
) -> list[AgentRunRead]:
    """Project direct objectives from the canonical AgentRun aggregate."""
    async with start_transaction(ro=True) as session:
        repository = AgentRunRepository(session)
        runs = await repository.list(
            organization_id=organization_id,
            limit=limit,
            offset=0,
            origin_kind=AgentRunOriginKind.OBJECTIVE,
            agent_id=agent_id,
            lifecycle=lifecycle,
        )
        return await _project_many(
            repository,
            runs,
            organization_id=organization_id,
        )


async def cancel_agent_run(
    *,
    organization_id: UUID,
    run_id: UUID,
    expected_state_revision: int,
) -> AgentRunCancellationRead:
    """Cancel unbound queued work or persist a request for a bound worker."""
    task_id: UUID | None = None
    async with start_transaction() as session:
        repository = AgentRunRepository(session)
        run = await repository.get(
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if run is None:
            raise AgentRunNotFound
        _require_revision(run.state_revision, expected_state_revision)

        cancellation_was_requested = run.cancellation_requested_at is not None
        disposition = _apply_cancellation(run)
        if disposition is AgentRunCancellationDisposition.CANCELLED:
            await release_agent_run_reservation_in_transaction(
                session,
                organization_id=organization_id,
                run_id=run_id,
            )
        await session.flush()
        if disposition is AgentRunCancellationDisposition.CANCELLED:
            await _file_agent_run_fact(
                session,
                run,
                event_type="agent.run.cancelled",
                payload={},
            )
        elif not cancellation_was_requested:
            await _file_agent_run_fact(
                session,
                run,
                event_type="agent.run.cancellation_requested",
                payload={},
            )
        projection = await _project_one(repository, run)
        result = AgentRunCancellationRead(
            disposition=disposition,
            run=projection,
        )
        if disposition is AgentRunCancellationDisposition.REQUESTED:
            task_id = run.absurd_task_id

    if task_id is not None:
        from eylo.modules.agent_runs.absurd import cancel_bound_agent_run

        await cancel_bound_agent_run(
            organization_id=organization_id,
            run_id=run_id,
            task_id=task_id,
        )
    return result


async def request_agent_run_cancellation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> UUID | None:
    """Persist an internal owner-driven cancellation; return a bound task ID."""
    run = await AgentRunRepository(session).get(
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if run is None:
        raise AgentRunNotFound
    if run.lifecycle in {
        AgentRunLifecycle.COMPLETED,
        AgentRunLifecycle.FAILED,
        AgentRunLifecycle.CANCELLED,
    }:
        return None
    cancellation_was_requested = run.cancellation_requested_at is not None
    disposition = _apply_cancellation(run)
    if disposition is AgentRunCancellationDisposition.CANCELLED:
        await release_agent_run_reservation_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
        )
    await session.flush()
    if disposition is AgentRunCancellationDisposition.CANCELLED:
        await _file_agent_run_fact(
            session,
            run,
            event_type="agent.run.cancelled",
            payload={},
        )
    elif not cancellation_was_requested:
        await _file_agent_run_fact(
            session,
            run,
            event_type="agent.run.cancellation_requested",
            payload={},
        )
    if disposition is AgentRunCancellationDisposition.REQUESTED:
        return run.absurd_task_id
    return None


async def accept_agent_run_cancellation(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> None:
    """Commit cancellation once the engine accepts it at a safe boundary."""
    async with start_transaction() as session:
        run = await AgentRunRepository(session).get(
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if run is None:
            raise AgentRunNotFound
        if run.lifecycle is AgentRunLifecycle.CANCELLED:
            return
        if run.lifecycle in {AgentRunLifecycle.COMPLETED, AgentRunLifecycle.FAILED}:
            return

        now = datetime.now(timezone.utc)
        if run.cancellation_requested_at is None:
            run.cancellation_requested_at = now
        run.lifecycle = AgentRunLifecycle.CANCELLED
        run.outcome = AgentRunOutcome.CANCELLED
        run.cancelled_at = now
        run.finished_at = now
        run.state_revision += 1
        await cancel_pending_input_requests_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
            cancelled_at=now,
        )
        await release_agent_run_reservation_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
        )
        await session.flush()
        await _file_agent_run_fact(
            session,
            run,
            event_type="agent.run.cancelled",
            payload={},
        )


async def answer_input_request(
    *,
    organization_id: UUID,
    run_id: UUID,
    request_id: UUID,
    member_id: UUID,
    command: AgentInputResponseRequest,
) -> AgentInputRequestRead:
    """Store one answer, then idempotently wake its named durable event."""
    event_name: str
    projection: AgentInputRequestRead
    async with start_transaction() as session:
        repository = AgentRunRepository(session)
        run = await repository.get(
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if run is None:
            raise AgentRunNotFound

        input_request = await repository.get_input_request(
            organization_id=organization_id,
            run_id=run_id,
            request_id=request_id,
            for_update=True,
        )
        if input_request is None:
            raise AgentInputRequestNotFound
        if run.cancellation_requested_at is not None:
            raise AgentRunConflict("A cancelling run cannot accept input.")

        normalized_response = to_jsonable_python(command.response)
        if input_request.status is AgentInputRequestStatus.ANSWERED:
            _require_answerable_lifecycle(run, input_request)
            if (
                input_request.answered_by_principal_kind
                is not InitiatingPrincipalKind.MEMBER
                or input_request.answered_by_principal_id != member_id
                or input_request.response != normalized_response
            ):
                raise AgentRunConflict(
                    "Input request was already answered with different semantics."
                )
        else:
            _require_revision(
                input_request.state_revision,
                command.expected_state_revision,
            )
            _require_answerable(run, input_request)
            _validate_input_response(input_request, normalized_response)

            now = datetime.now(timezone.utc)
            input_request.status = AgentInputRequestStatus.ANSWERED
            input_request.response = (
                JSON.NULL if command.response is None else normalized_response
            )
            input_request.answered_by_principal_kind = InitiatingPrincipalKind.MEMBER
            input_request.answered_by_principal_id = member_id
            input_request.answered_at = now
            input_request.state_revision += 1
            await session.flush()
            await session.refresh(input_request)
            await _file_agent_run_fact(
                session,
                run,
                event_type="agent.input.received",
                payload={
                    "input_request_id": str(input_request.id),
                    "request_kind": input_request.kind.value,
                },
                subject_type="agent.input",
                subject_id=input_request.id,
            )

        event_name = input_request.event_name
        projection = AgentInputRequestRead.model_validate(input_request)

    from eylo.modules.agent_runs.absurd import emit_agent_run_event

    await emit_agent_run_event(
        event_name=event_name,
        payload={
            "organization_id": str(organization_id),
            "run_id": str(run_id),
            "request_id": str(request_id),
        },
    )
    return projection


def _require_revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise AgentRunConflict(
            f"State revision conflict: expected {expected}, current {actual}."
        )


def _apply_cancellation(
    run: AgentRunModel,
) -> AgentRunCancellationDisposition:
    if run.lifecycle is AgentRunLifecycle.CANCELLED:
        return AgentRunCancellationDisposition.CANCELLED
    if run.lifecycle in {AgentRunLifecycle.COMPLETED, AgentRunLifecycle.FAILED}:
        raise AgentRunConflict(f"A {run.lifecycle.value} run cannot be cancelled.")
    if run.cancellation_requested_at is not None:
        return AgentRunCancellationDisposition.REQUESTED

    now = datetime.now(timezone.utc)
    run.cancellation_requested_at = now
    run.state_revision += 1
    if run.lifecycle is AgentRunLifecycle.QUEUED and run.absurd_task_id is None:
        run.lifecycle = AgentRunLifecycle.CANCELLED
        run.outcome = AgentRunOutcome.CANCELLED
        run.cancelled_at = now
        run.finished_at = now
        return AgentRunCancellationDisposition.CANCELLED
    return AgentRunCancellationDisposition.REQUESTED


async def _file_agent_run_fact(
    session: AsyncSession,
    run: AgentRunModel,
    *,
    event_type: str,
    payload: dict,
    subject_type: str = "agent.run",
    subject_id: UUID | None = None,
) -> None:
    if run.user_session_id is None:
        return
    await file_user_session_fact(
        session,
        organization_id=run.organization_id,
        user_session_id=run.user_session_id,
        subject_type=subject_type,
        subject_id=subject_id or run.id,
        event_type=event_type,
        payload={
            "agent_id": str(run.agent_id),
            "agent_revision": run.agent_revision,
            "run_id": str(run.id),
            **payload,
        },
    )


def _require_answerable(
    run: AgentRunModel,
    input_request: AgentInputRequestModel,
) -> None:
    if run.cancellation_requested_at is not None:
        raise AgentRunConflict("A cancelling run cannot accept input.")
    if input_request.status is not AgentInputRequestStatus.PENDING:
        raise AgentRunConflict(
            f"A {input_request.status.value} input request cannot be answered."
        )
    _require_answerable_lifecycle(run, input_request)


def _require_answerable_lifecycle(
    run: AgentRunModel,
    input_request: AgentInputRequestModel,
) -> None:
    expected_lifecycle = {
        AgentInputRequestKind.INPUT: AgentRunLifecycle.WAITING_FOR_INPUT,
        AgentInputRequestKind.APPROVAL: AgentRunLifecycle.WAITING_FOR_APPROVAL,
    }[input_request.kind]
    if run.lifecycle is not expected_lifecycle:
        raise AgentRunConflict(
            f"Run is {run.lifecycle.value}; expected {expected_lifecycle.value}."
        )


def _validate_input_response(
    input_request: AgentInputRequestModel,
    response: object,
) -> None:
    _require_json_size(
        response,
        max_bytes=_MAX_INPUT_RESPONSE_BYTES,
        label="Agent input response",
        error_type=AgentRunConflict,
    )
    try:
        Draft202012Validator(input_request.expected_response_schema).validate(response)
    except Exception as error:  # noqa: BLE001 - fail closed on resolver errors
        raise AgentRunConflict(
            "Input response does not match the expected response schema."
        ) from error

    if input_request.kind is not AgentInputRequestKind.APPROVAL:
        return
    if not isinstance(response, dict):
        raise AgentRunConflict("Approval response must be an object.")
    if set(response) - {"decision", "comment"}:
        raise AgentRunConflict("Approval response contains unsupported fields.")
    if response.get("decision") not in {"approve", "reject"}:
        raise AgentRunConflict("Approval decision must be approve or reject.")
    comment = response.get("comment")
    if comment is not None and not isinstance(comment, str):
        raise AgentRunConflict("Approval comment must be text.")


def _validated_response_schema(value: object) -> dict:
    normalized = to_jsonable_python(value)
    if not isinstance(normalized, dict):
        raise ValueError("Agent input response schema must be an object.")
    _require_json_size(
        normalized,
        max_bytes=_MAX_INPUT_SCHEMA_BYTES,
        label="Agent input response schema",
        error_type=ValueError,
    )
    node_count, depth = _json_shape(normalized)
    if node_count > _MAX_INPUT_SCHEMA_NODES or depth > _MAX_INPUT_SCHEMA_DEPTH:
        raise ValueError("Agent input response schema is too complex.")
    _reject_external_schema_references(normalized)
    try:
        Draft202012Validator.check_schema(normalized)
    except SchemaError as error:
        raise ValueError("Agent input response schema is invalid.") from error
    return normalized


def _reject_external_schema_references(value: object) -> None:
    """Keep response validation local and deterministic."""
    resources = [DRAFT202012.create_resource(value)]
    while resources:
        resource = resources.pop()
        contents = resource.contents
        if isinstance(contents, dict):
            for keyword in ("$ref", "$dynamicRef"):
                reference = contents.get(keyword)
                if reference is not None and (
                    not isinstance(reference, str)
                    or (reference and not reference.startswith("#"))
                ):
                    raise ValueError(
                        "Agent input response schema references must be local."
                    )
        resources.extend(resource.subresources())


def _require_json_size(
    value: object,
    *,
    max_bytes: int,
    label: str,
    error_type: type[Exception],
) -> None:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise error_type(f"{label} must be finite JSON data.") from error
    if len(encoded) > max_bytes:
        raise error_type(f"{label} exceeds {max_bytes} encoded bytes.")


def _json_shape(value: object, *, depth: int = 1) -> tuple[int, int]:
    if isinstance(value, dict):
        children = [_json_shape(item, depth=depth + 1) for item in value.values()]
    elif isinstance(value, list):
        children = [_json_shape(item, depth=depth + 1) for item in value]
    else:
        children = []
    if not children:
        return 1, depth
    return 1 + sum(count for count, _ in children), max(
        child_depth for _, child_depth in children
    )


async def _project_one(
    repository: AgentRunRepository,
    run: AgentRunModel,
) -> AgentRunRead:
    projected = await _project_many(
        repository,
        [run],
        organization_id=run.organization_id,
    )
    return projected[0]


async def _project_many(
    repository: AgentRunRepository,
    runs: Sequence[AgentRunModel],
    *,
    organization_id: UUID,
) -> list[AgentRunRead]:
    if not runs:
        return []
    run_ids = [run.id for run in runs]
    steps = await repository.list_steps(
        organization_id=organization_id,
        run_ids=run_ids,
    )
    input_requests = await repository.list_input_requests(
        organization_id=organization_id,
        run_ids=run_ids,
    )
    reservations = await repository.list_reservations(
        organization_id=organization_id,
        run_ids=run_ids,
    )
    steps_by_run = _group_steps(steps)
    requests_by_run = _group_input_requests(input_requests)
    reservations_by_run = {
        reservation.run_id: reservation for reservation in reservations
    }
    return [
        _project_run(
            run,
            reservation=reservations_by_run.get(run.id),
            steps=steps_by_run[run.id],
            input_requests=requests_by_run[run.id],
        )
        for run in runs
    ]


def _project_run(
    run: AgentRunModel,
    *,
    reservation: OrganizationExecutionReservationModel | None,
    steps: list[AgentRunStepRead],
    input_requests: list[AgentInputRequestRead],
) -> AgentRunRead:
    """Select the deliberate public fields; never spread an ORM row into an API."""
    return AgentRunRead(
        id=run.id,
        organization_id=run.organization_id,
        initiating_principal_kind=run.initiating_principal_kind,
        initiating_principal_id=run.initiating_principal_id,
        agent_id=run.agent_id,
        agent_revision=run.agent_revision,
        origin_kind=run.origin_kind,
        origin_message_id=run.origin_message_id,
        origin_schedule_run_id=run.origin_schedule_run_id,
        lifecycle=run.lifecycle,
        outcome=run.outcome,
        goal=run.goal,
        result=run.result,
        outcome_reason=run.outcome_reason,
        failure_summary=run.failure_summary,
        state_revision=run.state_revision,
        started_at=run.started_at,
        waiting_at=run.waiting_at,
        cancellation_requested_at=run.cancellation_requested_at,
        cancelled_at=run.cancelled_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        reservation=_project_reservation(reservation),
        steps=steps,
        input_requests=input_requests,
    )


def _project_reservation(
    reservation: OrganizationExecutionReservationModel | None,
) -> AgentRunReservationRead | None:
    if reservation is None:
        return None
    active_milliseconds = reservation.active_milliseconds
    if reservation.active_since is not None:
        elapsed = datetime.now(timezone.utc) - reservation.active_since
        active_milliseconds += max(0, int(elapsed.total_seconds() * 1000))
    return AgentRunReservationRead.model_validate(reservation).model_copy(
        update={"active_milliseconds": active_milliseconds}
    )


def _group_steps(
    steps: Sequence[AgentRunStepModel],
) -> defaultdict[UUID, list[AgentRunStepRead]]:
    grouped: defaultdict[UUID, list[AgentRunStepRead]] = defaultdict(list)
    for step in steps:
        grouped[step.run_id].append(AgentRunStepRead.model_validate(step))
    return grouped


def _group_input_requests(
    requests: Sequence[AgentInputRequestModel],
) -> defaultdict[UUID, list[AgentInputRequestRead]]:
    grouped: defaultdict[UUID, list[AgentInputRequestRead]] = defaultdict(list)
    for request in requests:
        grouped[request.run_id].append(AgentInputRequestRead.model_validate(request))
    return grouped
