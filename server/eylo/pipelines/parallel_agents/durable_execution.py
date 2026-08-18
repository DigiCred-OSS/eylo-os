"""Execute one immutable SYSTEM/TASK origin through the AgentRun workflow."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from eylo.common.contracts.background_task import TaskContent
from eylo.common.database import start_transaction
from eylo.modules.agent_runs.domain import (
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
    InitiatingPrincipalKind,
)
from eylo.modules.agent_runs.service import finish_agent_run_in_transaction
from eylo.modules.agent_runs.workflow import (
    AgentRunExecutionClaim,
    AgentRunWorkflowContext,
)
from eylo.modules.conversations.repositories.messages import MessageAgentRunRepository
from eylo.modules.conversations.schemas.message_content import SystemMessageContent
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
    RequestStatus,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.parallel_agents.schemas import TaskResultContent, WorkerResult
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.parallel_agents.background_agent_worker import (
    BackgroundAgentWorker,
)
from eylo.pipelines.parallel_agents.llm_task_worker import LLMTaskWorker
from eylo.pipelines.parallel_agents.swarm_agent_worker import SwarmAgentWorker

_HEARTBEAT_SECONDS = 120
_HEARTBEAT_INTERVAL_SECONDS = 30
_RESULT_LIMIT_BYTES = 65536

TaskRunner = Callable[
    [TaskContent, UUID, MessageInDb, UUID, AgentRunWorkflowContext],
    Awaitable[WorkerResult],
]


class ParallelAgentRunInvalid(Exception):
    """A persisted task no longer agrees with its immutable run authority."""


class ParallelTaskAgentRunExecutor:
    """Run one task message and atomically publish its canonical result."""

    def __init__(self, *, task_runner: TaskRunner | None = None) -> None:
        self._task_runner = task_runner or _run_task

    async def execute_origin(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
        origin: MessageInDb,
    ) -> None:
        try:
            task_content = await _validate_task_origin(claim, origin)
        except ParallelAgentRunInvalid:
            await _fail_task(claim, origin, "parallel_task_invalid")
            return

        await _mark_processing(origin.id)
        result_holder: list[WorkerResult] = []

        async def execute_task() -> None:
            result_holder.append(
                await self._task_runner(
                    task_content,
                    claim.organization_id,
                    origin,
                    claim.run_id,
                    context,
                )
            )

        try:
            await _run_with_heartbeat(context, execute_task)
        except NotConfiguredError:
            await _fail_task(claim, origin, "parallel_task_provider_not_configured")
            return
        try:
            await _persist_completion(
                claim=claim,
                origin=origin,
                task_content=task_content,
                worker_result=result_holder[0],
            )
        except ParallelAgentRunInvalid:
            await _fail_task(claim, origin, "parallel_task_result_invalid")


async def _validate_task_origin(
    claim: AgentRunExecutionClaim,
    origin: MessageInDb,
) -> TaskContent:
    if (
        claim.origin_kind is not AgentRunOriginKind.MESSAGE
        or claim.origin_message_id != origin.id
        or origin.kind != MessageKind.SYSTEM
        or origin.content_kind != MessageContentKind.TASK
        or origin.agent_run_id is not None
    ):
        raise ParallelAgentRunInvalid(
            "Parallel execution requires an unlinked system task origin."
        )
    if claim.principal.kind is not InitiatingPrincipalKind.WORKER:
        raise ParallelAgentRunInvalid(
            "Parallel execution requires an initiating agent."
        )
    try:
        task_content = TaskContent.from_json(origin.get_text_content())
    except ValueError as error:
        raise ParallelAgentRunInvalid("Parallel task content is invalid.") from error
    if task_content.source_agent_id != claim.principal.principal_id:
        raise ParallelAgentRunInvalid(
            "Parallel task source does not match its initiating agent."
        )
    try:
        task_content.require_execution_agent_ref(
            agent_id=claim.agent_id,
            agent_revision=claim.agent_revision,
        )
    except ValueError as error:
        raise ParallelAgentRunInvalid(
            "Parallel task target does not match its AgentRun authority."
        ) from error
    if claim.context_manifest.get("conversation_id") != str(origin.conversation_id):
        raise ParallelAgentRunInvalid(
            "Parallel task context does not match its conversation."
        )

    async with start_transaction(ro=True) as session:
        source_is_current = await MessageAgentRunRepository(
            session
        ).has_active_agent_sender_revision(
            conversation_id=origin.conversation_id,
            organization_id=claim.organization_id,
            sender_participant_id=origin.sender_participant_id,
            agent_id=task_content.source_agent_id,
            agent_revision=task_content.source_agent_revision,
        )
    if not source_is_current:
        raise ParallelAgentRunInvalid(
            "Parallel task source participant is no longer executable."
        )
    return task_content


async def _mark_processing(task_message_id: UUID) -> None:
    async with start_transaction() as session:
        await MessageService(session).update_(
            task_message_id,
            {"request_status": RequestStatus.PROCESSING},
        )


async def _run_task(
    task_content: TaskContent,
    organization_id: UUID,
    origin: MessageInDb,
    agent_run_id: UUID,
    durable_context: AgentRunWorkflowContext,
) -> WorkerResult:
    if task_content.background_agent_id is not None:
        return await BackgroundAgentWorker(
            task_content=task_content,
            organization_id=organization_id,
            conversation_id=origin.conversation_id,
            task_message_id=origin.id,
            agent_run_id=agent_run_id,
            durable_context=durable_context,
        ).run()
    if task_content.swarm_id is not None:
        return await SwarmAgentWorker(
            task_content=task_content,
            organization_id=organization_id,
            conversation_id=origin.conversation_id,
        ).run()
    return await LLMTaskWorker(
        task_content=task_content,
        organization_id=organization_id,
        conversation_id=origin.conversation_id,
        sender_id=origin.sender_participant_id,
    ).run()


async def _persist_completion(
    *,
    claim: AgentRunExecutionClaim,
    origin: MessageInDb,
    task_content: TaskContent,
    worker_result: WorkerResult,
) -> None:
    worker_type = _worker_type(task_content)
    task_status = (
        RequestStatus.SKIPPED
        if worker_result.outcome == "skipped"
        else RequestStatus.COMPLETED
    )
    result_content = TaskResultContent(
        result=worker_result.text,
        meta={
            "model_used": worker_result.model_used,
            "iterations_used": worker_result.iterations_used,
        },
    )
    projected_result = {
        "kind": "parallel_task",
        "task_message_id": str(origin.id),
        "task_status": task_status.value,
        "worker_type": worker_type,
        "model_used": worker_result.model_used,
        "iterations_used": worker_result.iterations_used,
        "output": worker_result.text,
    }
    _require_bounded_result(projected_result)

    async with start_transaction() as session:
        messages = MessageService(session)
        result_message = await messages.create_(
            MessageCreate(
                conversation_id=origin.conversation_id,
                sender_participant_id=origin.sender_participant_id,
                created_at=datetime.now(timezone.utc),
                kind=MessageKind.SYSTEM,
                content_kind=MessageContentKind.TASK_RESULT,
                content=SystemMessageContent(content=result_content.to_json()),
                parent_message_id=origin.id,
                request_id=None,
                request_status=task_status,
                agent_run_id=claim.run_id,
                meta={
                    "worker_type": worker_type,
                    "model_used": worker_result.model_used,
                    "iterations_used": worker_result.iterations_used,
                },
            )
        )
        await messages.update_(
            origin.id,
            {"request_status": task_status},
        )
        projected_result["task_result_message_id"] = str(result_message.id)
        _require_bounded_result(projected_result)
        await finish_agent_run_in_transaction(
            session,
            organization_id=claim.organization_id,
            run_id=claim.run_id,
            lifecycle=AgentRunLifecycle.COMPLETED,
            outcome=AgentRunOutcome.ACHIEVED,
            result=projected_result,
            outcome_reason=(
                "No work was required." if worker_result.outcome == "skipped" else None
            ),
        )


async def _fail_task(
    claim: AgentRunExecutionClaim,
    origin: MessageInDb,
    summary: str,
) -> None:
    task_meta = origin.meta.model_dump(mode="json") if origin.meta else {}
    async with start_transaction() as session:
        await MessageService(session).update_(
            origin.id,
            {
                "request_status": RequestStatus.FAILED,
                "meta": {**task_meta, "error": summary},
            },
        )
        await finish_agent_run_in_transaction(
            session,
            organization_id=claim.organization_id,
            run_id=claim.run_id,
            lifecycle=AgentRunLifecycle.FAILED,
            outcome=AgentRunOutcome.FAILED,
            failure_summary=summary,
        )


def _require_bounded_result(result: dict) -> None:
    encoded = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > _RESULT_LIMIT_BYTES:
        raise ParallelAgentRunInvalid(
            "Parallel task result exceeds the canonical 65536-byte limit."
        )


def _worker_type(task_content: TaskContent) -> str:
    if task_content.background_agent_id is not None:
        return "background_agent"
    if task_content.swarm_id is not None:
        return "swarm_agent"
    return "llm_task"


async def _run_with_heartbeat(
    context: AgentRunWorkflowContext,
    operation: Callable[[], Awaitable[None]],
) -> None:
    operation_task = asyncio.create_task(operation())
    try:
        while not operation_task.done():
            remaining_milliseconds = await context.heartbeat(seconds=_HEARTBEAT_SECONDS)
            try:
                await asyncio.wait_for(
                    asyncio.shield(operation_task),
                    timeout=min(
                        _HEARTBEAT_INTERVAL_SECONDS,
                        max(0.001, remaining_milliseconds / 1000),
                    ),
                )
            except TimeoutError:
                continue
        await operation_task
    finally:
        if not operation_task.done():
            operation_task.cancel()
            try:
                await operation_task
            except asyncio.CancelledError:
                pass


__all__ = ["ParallelAgentRunInvalid", "ParallelTaskAgentRunExecutor"]
