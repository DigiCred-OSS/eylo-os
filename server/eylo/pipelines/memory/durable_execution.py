"""Absurd filing and execution for post-conversation memory formation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask
from pydantic import ValidationError
from sqlalchemy import and_, exists, func, or_, select, text, tuple_
from sqlalchemy.orm import aliased

from eylo.absurd_work import (
    AbsurdBoundWorkService,
    DurableState,
    DurableWorkBindingPending,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.contracts.embedding import embedding_space_from_record
from eylo.common.contracts.memory import (
    MEMORY_MAX_WINDOW_MESSAGES,
    MemoryError,
    MemoryInputMessage,
    MemoryLevel,
    MemoryMessageRole,
    MemoryOperation,
    MemoryOrigin,
    MemoryOutcomeCounts,
    MemoryScope,
    MemorySourceReference,
)
from eylo.common.contracts.messages import MessageInDb, MessageKind
from eylo.common.database import start_transaction
from eylo.durable_runtime import (
    DURABLE_MAX_ATTEMPTS,
    PlatformDurableRuntime,
    run_with_durable_heartbeat,
)
from eylo.events.schema.py_events.memory import MemoryWorkTransition
from eylo.modules.agent_runs.budgets import (
    activate_memory_formation_reservation_in_transaction,
    check_memory_formation_active_time,
    memory_formation_execution_budget_scope,
    release_memory_formation_reservation_in_transaction,
    require_memory_formation_usage_reported,
    reserve_memory_formation_in_transaction,
)
from eylo.modules.agent_runs.domain import (
    ExecutionBudgetDimension,
    ExecutionBudgetError,
    ExecutionBudgetExceeded,
    ExecutionBudgetNotConfigured,
    ExecutionBudgetUnavailable,
    ExecutionUsageNotReported,
)
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.message_content import text_from_content_blocks
from eylo.modules.memory.events import (
    register_formation_fact_changes,
    register_formation_lifecycle,
)
from eylo.modules.memory.models import (
    MemoryFormationCursorModel,
    MemoryFormationEffectModel,
    MemoryFormationJobModel,
)
from eylo.modules.memory.reindex_service import MemoryReindexService
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.memory.resolver import resolve_memory_runtime

logger = logging.getLogger(__name__)

MEMORY_FORMATION_WORKFLOW = "eylo.memory.form.v1"
_MEMORY_TOOL_NAMES = (
    "memory_forget",
    "memory_recall",
    "memory_refresh",
    "memory_remember",
)


@dataclass(frozen=True, order=True, slots=True)
class _MessagePosition:
    created_at: datetime
    message_id: UUID


@dataclass(frozen=True, slots=True)
class _CancellationResult:
    cancelled: bool
    task_id: UUID | None


def register_memory_formation_workflow(runtime: PlatformDurableRuntime) -> None:
    workflow = MemoryFormationWorkflow()
    runtime.register_task(
        name=MEMORY_FORMATION_WORKFLOW,
        handler=workflow.execute,
    )


async def enqueue_memory_formation(
    *,
    scope: MemoryScope,
    memory_provider_config_id: UUID,
    memory_provider_config_revision: int,
) -> UUID | None:
    """Advance the requested watermark and file at most one active generation."""
    async with start_transaction() as session:
        await _lock_cursor_key(session, scope)
        conversation_id = await session.scalar(
            select(ConversationsModel.id).where(
                ConversationsModel.id == scope.conversation_id,
                ConversationsModel.organization_id == scope.organization_id,
                ConversationsModel.deleted.is_(False),
            )
        )
        if conversation_id is None:
            raise MemoryError("Memory conversation authority is unavailable.")

        requested = await _latest_message_position(session, scope)
        if requested is None:
            return None
        cursor = await _get_or_create_cursor(
            session,
            scope=scope,
            memory_provider_config_id=memory_provider_config_id,
            memory_provider_config_revision=memory_provider_config_revision,
        )
        prior_requested = _position_from_cursor(cursor, requested=True)
        if prior_requested is None or requested > prior_requested:
            _set_requested_position(cursor, requested)
        cursor.memory_provider_config_id = memory_provider_config_id
        cursor.memory_provider_config_revision = memory_provider_config_revision
        await _clear_explicitly_retryable_fence(session, cursor)
        if cursor.active_job_id is not None or not _cursor_has_backlog(cursor):
            return None

        job = await _file_cursor_job(session, cursor)
        if job is None:
            return None
        job_id = job.id

    try:
        await spawn_memory_formation(
            organization_id=scope.organization_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001 - committed DB outbox is recoverable
        logger.warning(
            "Could not immediately spawn memory formation %s: %s",
            job_id,
            type(error).__name__,
        )
    return job_id


async def _clear_explicitly_retryable_fence(
    session,
    cursor: MemoryFormationCursorModel,
) -> None:
    """Let a new enqueue retry a terminal failure; periodic scans stay fenced."""
    if cursor.active_job_id is None:
        return
    state = await session.scalar(
        select(MemoryFormationJobModel.state).where(
            MemoryFormationJobModel.id == cursor.active_job_id,
            MemoryFormationJobModel.organization_id == cursor.organization_id,
            MemoryFormationJobModel.conversation_id == cursor.conversation_id,
            MemoryFormationJobModel.deleted.is_(False),
        )
    )
    if state is DurableState.FAILED:
        cursor.active_job_id = None
        await session.flush()


async def _lock_cursor_key(session, scope: MemoryScope) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"memory:{scope.organization_id}:{scope.conversation_id}"},
    )


async def _get_or_create_cursor(
    session,
    *,
    scope: MemoryScope,
    memory_provider_config_id: UUID,
    memory_provider_config_revision: int,
) -> MemoryFormationCursorModel:
    cursor = await session.scalar(
        select(MemoryFormationCursorModel)
        .where(
            MemoryFormationCursorModel.organization_id == scope.organization_id,
            MemoryFormationCursorModel.conversation_id == scope.conversation_id,
            MemoryFormationCursorModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if cursor is not None:
        return cursor
    cursor = MemoryFormationCursorModel(
        organization_id=scope.organization_id,
        conversation_id=scope.conversation_id,
        memory_provider_config_id=memory_provider_config_id,
        memory_provider_config_revision=memory_provider_config_revision,
    )
    session.add(cursor)
    await session.flush()
    return cursor


def _position_from_cursor(
    cursor: MemoryFormationCursorModel,
    *,
    requested: bool,
) -> _MessagePosition | None:
    created_at = (
        cursor.requested_through_created_at
        if requested
        else cursor.processed_through_created_at
    )
    message_id = (
        cursor.requested_through_message_id
        if requested
        else cursor.processed_through_message_id
    )
    if created_at is None or message_id is None:
        return None
    return _MessagePosition(created_at=created_at, message_id=message_id)


def _set_requested_position(
    cursor: MemoryFormationCursorModel,
    position: _MessagePosition,
) -> None:
    cursor.requested_through_created_at = position.created_at
    cursor.requested_through_message_id = position.message_id


def _cursor_has_backlog(cursor: MemoryFormationCursorModel) -> bool:
    requested = _position_from_cursor(cursor, requested=True)
    processed = _position_from_cursor(cursor, requested=False)
    return requested is not None and (processed is None or requested > processed)


def _eligible_message_query(scope: MemoryScope, *entities: Any):
    """Select learnable messages, excluding requests that operated on Memory."""
    tool_message = aliased(MessagesModel)
    memory_tool_in_request = exists(
        select(tool_message.id).where(
            tool_message.conversation_id == MessagesModel.conversation_id,
            tool_message.request_id == MessagesModel.request_id,
            tool_message.kind == MessageKind.TOOL_USE.value,
            tool_message.deleted.is_(False),
            func.split_part(
                tool_message.content["content"]["name"].astext,
                "__",
                1,
            ).in_(_MEMORY_TOOL_NAMES),
        )
    )
    return (
        select(*entities)
        .join(
            ConversationsModel,
            ConversationsModel.id == MessagesModel.conversation_id,
        )
        .join(
            ParticipantsModel,
            and_(
                ParticipantsModel.id == MessagesModel.sender_participant_id,
                ParticipantsModel.conversation_id == MessagesModel.conversation_id,
            ),
        )
        .where(
            ConversationsModel.id == scope.conversation_id,
            ConversationsModel.organization_id == scope.organization_id,
            ConversationsModel.deleted.is_(False),
            MessagesModel.deleted.is_(False),
            ParticipantsModel.deleted.is_(False),
            MessagesModel.kind.in_(
                [MessageKind.USER.value, MessageKind.ASSISTANT.value]
            ),
            ~memory_tool_in_request,
        )
    )


def _eligible_messages(scope: MemoryScope):
    return _eligible_message_query(
        scope,
        MessagesModel.created_at,
        MessagesModel.id,
    )


async def _latest_message_position(
    session,
    scope: MemoryScope,
) -> _MessagePosition | None:
    row = (
        await session.execute(
            _eligible_messages(scope)
            .order_by(MessagesModel.created_at.desc(), MessagesModel.id.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    return _MessagePosition(created_at=row.created_at, message_id=row.id)


async def _next_window_positions(
    session,
    cursor: MemoryFormationCursorModel,
) -> list[_MessagePosition]:
    scope = MemoryScope(
        organization_id=cursor.organization_id,
        level=MemoryLevel.CONVERSATION,
        owner_id=cursor.conversation_id,
    )
    requested = _position_from_cursor(cursor, requested=True)
    if requested is None:
        return []
    query = _eligible_messages(scope).where(
        tuple_(MessagesModel.created_at, MessagesModel.id)
        <= tuple_(requested.created_at, requested.message_id)
    )
    processed = _position_from_cursor(cursor, requested=False)
    if processed is not None:
        query = query.where(
            tuple_(MessagesModel.created_at, MessagesModel.id)
            > tuple_(processed.created_at, processed.message_id)
        )
    rows = (
        await session.execute(
            query.order_by(
                MessagesModel.created_at.asc(), MessagesModel.id.asc()
            ).limit(MEMORY_MAX_WINDOW_MESSAGES)
        )
    ).all()
    return [
        _MessagePosition(created_at=row.created_at, message_id=row.id) for row in rows
    ]


async def _file_cursor_job(
    session,
    cursor: MemoryFormationCursorModel,
) -> MemoryFormationJobModel | None:
    positions = await _next_window_positions(session, cursor)
    if not positions:
        return None
    through = positions[-1]
    processed = _position_from_cursor(cursor, requested=False)
    locked_space = await MemoryReindexService(session).lock_active_space(
        organization_id=cursor.organization_id,
        memory_provider_config_id=cursor.memory_provider_config_id,
    )
    runtime = await resolve_memory_runtime(
        cursor.organization_id,
        session,
        provider_config_id=cursor.memory_provider_config_id,
        provider_config_revision=cursor.memory_provider_config_revision,
    )
    space = runtime.embedding_space
    if not space.is_compatible_with(locked_space):
        raise MemoryError("Memory formation filing crossed an index cutover.")
    job = MemoryFormationJobModel(
        organization_id=cursor.organization_id,
        conversation_id=cursor.conversation_id,
        generation=cursor.next_generation,
        range_start_created_at=None if processed is None else processed.created_at,
        range_start_message_id=None if processed is None else processed.message_id,
        range_through_created_at=through.created_at,
        range_through_message_id=through.message_id,
        message_count=len(positions),
        memory_provider_config_id=runtime.authority.provider_config_id,
        memory_provider_config_revision=runtime.authority.provider_config_revision,
        embedding_provider_config_id=space.provider_config_id,
        embedding_provider_config_revision=space.provider_config_revision,
        embedding_provider=space.provider,
        embedding_endpoint=space.endpoint,
        embedding_model=space.model,
        embedding_dimensions=space.dimensions,
        embedding_semantic_options=dict(space.semantic_options),
        embedding_space_id=space.id,
        extraction_llm_provider_config_id=(
            runtime.extraction_authority.provider_config_id
        ),
        extraction_llm_provider_config_revision=(
            runtime.extraction_authority.provider_config_revision
        ),
        extraction_llm_provider=runtime.extraction_authority.provider,
        extraction_llm_model=runtime.extraction_authority.model,
        extraction_prompt_revision=runtime.extraction_authority.prompt_revision,
        max_attempts=DURABLE_MAX_ATTEMPTS,
    )
    session.add(job)
    await session.flush()
    await reserve_memory_formation_in_transaction(
        session,
        organization_id=cursor.organization_id,
        job_id=job.id,
    )
    cursor.active_job_id = job.id
    cursor.next_generation += 1
    await session.flush()
    register_formation_lifecycle(job, MemoryWorkTransition.QUEUED)
    return job


async def file_memory_formation_backlog(*, limit: int = 100) -> int:
    """File cursor backlog left by a crash or a newly completed page."""
    async with start_transaction(ro=True) as session:
        cursor_ids = list(
            (
                await session.execute(
                    select(MemoryFormationCursorModel.id)
                    .where(
                        MemoryFormationCursorModel.active_job_id.is_(None),
                        MemoryFormationCursorModel.requested_through_created_at.is_not(
                            None
                        ),
                        MemoryFormationCursorModel.deleted.is_(False),
                        or_(
                            MemoryFormationCursorModel.processed_through_created_at.is_(
                                None
                            ),
                            tuple_(
                                MemoryFormationCursorModel.requested_through_created_at,
                                MemoryFormationCursorModel.requested_through_message_id,
                            )
                            > tuple_(
                                MemoryFormationCursorModel.processed_through_created_at,
                                MemoryFormationCursorModel.processed_through_message_id,
                            ),
                        ),
                    )
                    .order_by(MemoryFormationCursorModel.updated_at.asc())
                    .limit(limit)
                )
            ).scalars()
        )
    filed = 0
    for cursor_id in cursor_ids:
        try:
            async with start_transaction() as session:
                cursor = await session.scalar(
                    select(MemoryFormationCursorModel)
                    .where(
                        MemoryFormationCursorModel.id == cursor_id,
                        MemoryFormationCursorModel.active_job_id.is_(None),
                        MemoryFormationCursorModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
                if cursor is None or not _cursor_has_backlog(cursor):
                    continue
                if await _file_cursor_job(session, cursor) is not None:
                    filed += 1
        except Exception as error:  # noqa: BLE001 - periodic retry remains available
            logger.warning(
                "Could not file memory cursor backlog: %s",
                type(error).__name__,
            )
    return filed


async def spawn_memory_formation(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=MemoryFormationJobModel,
        organization_id=organization_id,
        work_id=job_id,
        workflow_name=MEMORY_FORMATION_WORKFLOW,
        params_name="job_id",
        idempotency_prefix="memory-formation",
    )


async def spawn_unbound_memory_formations(*, limit: int = 100) -> int:
    await file_memory_formation_backlog(limit=limit)

    async def spawn(organization_id: UUID, job_id: UUID) -> UUID:
        return await spawn_memory_formation(
            organization_id=organization_id,
            job_id=job_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=MemoryFormationJobModel,
        spawn=spawn,
        limit=limit,
    )
    for job_id, error in failures:
        logger.error(
            "Could not spawn memory formation %s: %s",
            job_id,
            type(error).__name__,
        )
    return spawned


async def cancel_memory_formation(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> bool:
    result = await _commit_memory_cancellation(
        organization_id=organization_id,
        job_id=job_id,
    )
    if result.cancelled and result.task_id is not None:
        runtime = PlatformDurableRuntime()
        try:
            await runtime.cancel_task(result.task_id)
        finally:
            await runtime.close()
    return result.cancelled


async def _commit_memory_cancellation(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> _CancellationResult:
    """Cancel product work, release capacity, and settle its cursor atomically."""
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(MemoryFormationJobModel, session)
        job = await service.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        cancelled, task_id = await service.cancel(
            work_id=job_id,
            organization_id=organization_id,
        )
        if not cancelled:
            return _CancellationResult(cancelled=False, task_id=task_id)

        cursor = await _locked_job_cursor(session, job)
        if cursor is not None:
            effect = await session.scalar(
                select(MemoryFormationEffectModel).where(
                    MemoryFormationEffectModel.formation_job_id == job.id,
                    MemoryFormationEffectModel.organization_id == job.organization_id,
                    MemoryFormationEffectModel.deleted.is_(False),
                )
            )
            if effect is not None and effect.finished_at is not None:
                counts = _counts_from_effect(effect)
                _set_job_outcomes(job, counts)
                _advance_processed_cursor(cursor, job)
            else:
                _discard_requested_backlog(cursor)
            cursor.active_job_id = None
        await release_memory_formation_reservation_in_transaction(
            session,
            organization_id=organization_id,
            job_id=job_id,
        )
        register_formation_lifecycle(
            job,
            MemoryWorkTransition.CANCELLED,
            outcomes=_counts_from_job(job),
        )
        return _CancellationResult(cancelled=True, task_id=task_id)


class MemoryFormationWorkflow:
    """Extract one immutable operation plan and apply it exactly once per job."""

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, job_id = _parse_params(params)
        try:
            return await self._execute(
                organization_id=organization_id,
                job_id=job_id,
                task_context=task_context,
            )
        except CancelledTask:
            await _commit_memory_cancellation(
                organization_id=organization_id,
                job_id=job_id,
            )
            raise

    async def _execute(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        try:
            async with start_transaction() as session:
                job = await AbsurdBoundWorkService(
                    MemoryFormationJobModel,
                    session,
                ).begin_attempt(
                    work_id=job_id,
                    organization_id=organization_id,
                )
                if job.state in {
                    DurableState.SUCCEEDED,
                    DurableState.FAILED,
                    DurableState.CANCELLED,
                }:
                    return _receipt(job)
                register_formation_lifecycle(
                    job,
                    MemoryWorkTransition.ATTEMPT_STARTED,
                )
            async with start_transaction() as session:
                job = await AbsurdBoundWorkService(
                    MemoryFormationJobModel,
                    session,
                ).get(
                    work_id=job_id,
                    organization_id=organization_id,
                    for_update=True,
                )
                if job.state in {
                    DurableState.SUCCEEDED,
                    DurableState.FAILED,
                    DurableState.CANCELLED,
                }:
                    return _receipt(job)
                if job.state is not DurableState.RUNNING:
                    raise MemoryError("Memory formation attempt is not running.")
                _validate_job_range(job)
                cursor = await _locked_job_cursor(session, job)
                if cursor is None:
                    raise MemoryError(
                        "Memory formation generation has no active cursor fence."
                    )
                await activate_memory_formation_reservation_in_transaction(
                    session,
                    organization_id=organization_id,
                    job_id=job_id,
                )
                scope = MemoryScope(
                    organization_id=job.organization_id,
                    level=MemoryLevel.CONVERSATION,
                    owner_id=job.conversation_id,
                )
                embedding_space = embedding_space_from_record(job)
                if embedding_space is None:
                    raise MemoryError(
                        "Memory formation job has no embedding authority."
                    )
                runtime = await resolve_memory_runtime(
                    job.organization_id,
                    session,
                    provider_config_id=job.memory_provider_config_id,
                    provider_config_revision=job.memory_provider_config_revision,
                    embedding_space=embedding_space,
                )
                _validate_extraction_authority(job, runtime)
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        try:
            messages = await _messages_in_job_range(job)
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        async def form() -> list[dict[str, Any]]:
            with memory_formation_execution_budget_scope(
                organization_id=organization_id,
                job_id=job_id,
            ):
                operations = await runtime.adapter.add(
                    messages,
                    scope=scope,
                    source_conversation_id=job.conversation_id,
                    origin=MemoryOrigin.AUTOMATIC_FORMATION,
                    actor=None,
                    formation_job_id=job_id,
                )
            return [operation.model_dump(mode="json") for operation in operations]

        try:
            remaining_milliseconds = await check_memory_formation_active_time(
                organization_id=organization_id,
                job_id=job_id,
            )
            if remaining_milliseconds <= 0:
                raise ExecutionBudgetExceeded(ExecutionBudgetDimension.ACTIVE_TIME)
            try:
                async with asyncio.timeout(remaining_milliseconds / 1_000):
                    payload = await task_context.step(
                        f"memory-formation:{job_id}:apply:v2",
                        lambda: run_with_durable_heartbeat(task_context, form),
                    )
            except TimeoutError:
                raise ExecutionBudgetExceeded(
                    ExecutionBudgetDimension.ACTIVE_TIME
                ) from None
            operations = [MemoryOperation.model_validate(item) for item in payload]
            await require_memory_formation_usage_reported(
                organization_id=organization_id,
                job_id=job_id,
            )
            outcomes = MemoryOutcomeCounts.from_operations(operations)
        except Exception as error:  # noqa: BLE001 - work failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        try:
            async with start_transaction() as session:
                service = AbsurdBoundWorkService(
                    MemoryFormationJobModel,
                    session,
                )
                current = await service.get(
                    work_id=job_id,
                    organization_id=organization_id,
                    for_update=True,
                )
                already_succeeded = current.state is DurableState.SUCCEEDED
                row = await service.succeed(
                    work_id=job_id,
                    organization_id=organization_id,
                    values=_outcome_values(outcomes),
                )
                if row.state is DurableState.SUCCEEDED and not already_succeeded:
                    cursor = await _locked_job_cursor(session, row)
                    if cursor is None:
                        raise MemoryError(
                            "Memory formation succeeded without its cursor fence."
                        )
                    _advance_processed_cursor(cursor, row)
                    cursor.active_job_id = None
                exceeded = await release_memory_formation_reservation_in_transaction(
                    session,
                    organization_id=organization_id,
                    job_id=job_id,
                )
                if exceeded is not None:
                    raise ExecutionBudgetExceeded(exceeded)
                if row.state is DurableState.SUCCEEDED and not already_succeeded:
                    register_formation_lifecycle(
                        row,
                        MemoryWorkTransition.SUCCEEDED,
                        outcomes=outcomes,
                    )
                    register_formation_fact_changes(row, operations)
                receipt = _receipt(row)
        except Exception as error:  # noqa: BLE001 - projection failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )
        if row.state is DurableState.SUCCEEDED:
            await _continue_memory_backlog(row)
        return receipt


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "job_id"}:
        raise ValueError("Memory formation task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["job_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Memory formation task params contain an invalid UUID."
        ) from error


def _validate_extraction_authority(job, runtime) -> None:
    authority = runtime.extraction_authority
    if (
        authority.provider_config_id != job.extraction_llm_provider_config_id
        or authority.provider_config_revision
        != job.extraction_llm_provider_config_revision
        or authority.provider != job.extraction_llm_provider
        or authority.model != job.extraction_llm_model
        or authority.prompt_revision != job.extraction_prompt_revision
    ):
        raise MemoryError("Memory extraction authority changed before execution.")


async def _handle_failure(
    *,
    organization_id: UUID,
    job_id: UUID,
    error: Exception,
    permanent: bool,
) -> dict[str, Any]:
    summary = _safe_failure_summary(error)
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(
            MemoryFormationJobModel,
            session,
        )
        row = await service.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = row.state is DurableState.RUNNING
        state = await service.fail(
            work_id=job_id,
            organization_id=organization_id,
            error=summary,
            permanent=permanent,
        )
        if state is DurableState.FAILED:
            _set_job_outcomes(row, MemoryOutcomeCounts.one_failure())
        await release_memory_formation_reservation_in_transaction(
            session,
            organization_id=organization_id,
            job_id=job_id,
        )
        if was_running:
            register_formation_lifecycle(
                row,
                (
                    MemoryWorkTransition.RETRY_SCHEDULED
                    if state is DurableState.PENDING
                    else MemoryWorkTransition.FAILED
                ),
                outcomes=(
                    _counts_from_job(row)
                    if state is DurableState.FAILED
                    else None
                ),
                failure_code=summary,
            )
        receipt = _receipt(row)
    if state is DurableState.PENDING:
        raise MemoryError(
            "Memory formation retry requested.",
            retryable=True,
        ) from None
    if state is DurableState.FAILED:
        logger.warning("Memory formation %s failed: %s", job_id, summary)
    return receipt


def _safe_failure_summary(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "memory_dependency_not_configured"
    if isinstance(error, ExecutionBudgetNotConfigured):
        return "memory_execution_budget_not_configured"
    if isinstance(error, ExecutionBudgetUnavailable):
        return f"memory_execution_capacity_{error.dimension.value}_unavailable"
    if isinstance(error, ExecutionBudgetExceeded):
        return f"memory_execution_{error.dimension.value}_limit_exceeded"
    if isinstance(error, ExecutionUsageNotReported):
        return "memory_execution_usage_not_reported"
    if isinstance(error, ExecutionBudgetError):
        return "memory_execution_budget_conflict"
    if isinstance(error, MemoryError):
        return (
            "memory_provider_retryable_failure"
            if error.retryable
            else "memory_contract_failure"
        )
    return "memory_internal_failure"


def _is_permanent(error: Exception) -> bool:
    return (
        isinstance(
            error,
            (
                NotConfiguredError,
                ExecutionBudgetNotConfigured,
                ExecutionBudgetExceeded,
                ExecutionUsageNotReported,
            ),
        )
        or (
            isinstance(error, ExecutionBudgetError)
            and not isinstance(error, ExecutionBudgetUnavailable)
        )
        or (isinstance(error, MemoryError) and not error.retryable)
    )


async def _messages_in_job_range(
    job: MemoryFormationJobModel,
) -> list[MemoryInputMessage]:
    scope = MemoryScope(
        organization_id=job.organization_id,
        level=MemoryLevel.CONVERSATION,
        owner_id=job.conversation_id,
    )
    query = (
        _eligible_message_query(scope, MessagesModel, ParticipantsModel)
        .where(
            tuple_(MessagesModel.created_at, MessagesModel.id)
            <= tuple_(
                job.range_through_created_at,
                job.range_through_message_id,
            )
        )
        .order_by(MessagesModel.created_at.asc(), MessagesModel.id.asc())
        .limit(MEMORY_MAX_WINDOW_MESSAGES + 1)
    )
    if job.range_start_created_at is not None:
        query = query.where(
            tuple_(MessagesModel.created_at, MessagesModel.id)
            > tuple_(job.range_start_created_at, job.range_start_message_id)
        )
    async with start_transaction(ro=True) as session:
        rows = (await session.execute(query)).all()

    if len(rows) != job.message_count:
        raise MemoryError("Memory formation message range changed before execution.")
    final_message = rows[-1][0]
    final_position = _MessagePosition(
        created_at=final_message.created_at,
        message_id=final_message.id,
    )
    expected_through = _MessagePosition(
        created_at=job.range_through_created_at,
        message_id=job.range_through_message_id,
    )
    if final_position != expected_through:
        raise MemoryError("Memory formation message watermark is inconsistent.")

    messages: list[MemoryInputMessage] = []
    for message, participant in rows:
        messages.append(_memory_input_from_row(message, participant))
    return messages


def _memory_input_from_row(message, participant) -> MemoryInputMessage:
    try:
        record = MessageInDb.model_validate(message)
        content = getattr(record.content, "content", None)
        if content is None:
            raise MemoryError("Memory formation message has no text content.")
        content_text = (
            content if isinstance(content, str) else text_from_content_blocks(content)
        )
        if not content_text or not content_text.strip():
            raise MemoryError("Memory formation message has empty text content.")
        role = (
            MemoryMessageRole.ASSISTANT
            if record.kind is MessageKind.ASSISTANT
            else MemoryMessageRole.USER
        )
        return MemoryInputMessage(
            role=role,
            content=content_text.strip(),
            sources=(
                MemorySourceReference(
                    message_id=message.id,
                    participant_id=participant.id,
                    agent_id=participant.agent_id,
                    agent_revision=participant.agent_revision,
                ),
            ),
        )
    except MemoryError:
        raise
    except (TypeError, ValueError):
        raise MemoryError("Memory formation message contract is invalid.") from None


def _receipt(job: MemoryFormationJobModel) -> dict[str, Any]:
    return {
        "organization_id": str(job.organization_id),
        "job_id": str(job.id),
        "state": job.state.value,
        "generation": job.generation,
        "range": {
            "after": _position_json(
                job.range_start_created_at,
                job.range_start_message_id,
            ),
            "through": _position_json(
                job.range_through_created_at,
                job.range_through_message_id,
            ),
            "message_count": job.message_count,
        },
        "outcomes": _counts_from_job(job).model_dump(mode="json"),
    }


def _validate_job_range(job: MemoryFormationJobModel) -> None:
    if not 1 <= job.message_count <= MEMORY_MAX_WINDOW_MESSAGES:
        raise MemoryError("Memory formation message count is outside its limit.")
    through = _MessagePosition(
        created_at=job.range_through_created_at,
        message_id=job.range_through_message_id,
    )
    if (job.range_start_created_at is None) != (job.range_start_message_id is None):
        raise MemoryError("Memory formation start watermark is incomplete.")
    if job.range_start_created_at is not None:
        start = _MessagePosition(
            created_at=job.range_start_created_at,
            message_id=job.range_start_message_id,
        )
        if through <= start:
            raise MemoryError("Memory formation range does not advance.")


async def _locked_job_cursor(
    session,
    job: MemoryFormationJobModel,
) -> MemoryFormationCursorModel | None:
    return await session.scalar(
        select(MemoryFormationCursorModel)
        .where(
            MemoryFormationCursorModel.organization_id == job.organization_id,
            MemoryFormationCursorModel.conversation_id == job.conversation_id,
            MemoryFormationCursorModel.active_job_id == job.id,
            MemoryFormationCursorModel.deleted.is_(False),
        )
        .with_for_update()
    )


def _advance_processed_cursor(
    cursor: MemoryFormationCursorModel,
    job: MemoryFormationJobModel,
) -> None:
    current = _position_from_cursor(cursor, requested=False)
    expected = (
        None
        if job.range_start_created_at is None
        else _MessagePosition(
            created_at=job.range_start_created_at,
            message_id=job.range_start_message_id,
        )
    )
    if current != expected:
        raise MemoryError("Memory formation processed watermark changed.")
    through = _MessagePosition(
        created_at=job.range_through_created_at,
        message_id=job.range_through_message_id,
    )
    requested = _position_from_cursor(cursor, requested=True)
    if requested is None or requested < through:
        raise MemoryError("Memory formation exceeded its requested watermark.")
    cursor.processed_through_created_at = through.created_at
    cursor.processed_through_message_id = through.message_id


def _discard_requested_backlog(cursor: MemoryFormationCursorModel) -> None:
    cursor.requested_through_created_at = cursor.processed_through_created_at
    cursor.requested_through_message_id = cursor.processed_through_message_id


def _outcome_values(outcomes: MemoryOutcomeCounts) -> dict[str, int]:
    return {
        "considered_count": outcomes.considered,
        "added_count": outcomes.added,
        "updated_count": outcomes.updated,
        "deleted_count": outcomes.deleted,
        "noop_count": outcomes.noop,
        "failed_count": outcomes.failed,
    }


def _set_job_outcomes(
    job: MemoryFormationJobModel,
    outcomes: MemoryOutcomeCounts,
) -> None:
    for field_name, value in _outcome_values(outcomes).items():
        setattr(job, field_name, value)


def _counts_from_job(job: MemoryFormationJobModel) -> MemoryOutcomeCounts:
    return MemoryOutcomeCounts(
        considered=job.considered_count,
        added=job.added_count,
        updated=job.updated_count,
        deleted=job.deleted_count,
        noop=job.noop_count,
        failed=job.failed_count,
    )


def _counts_from_effect(
    effect: MemoryFormationEffectModel,
) -> MemoryOutcomeCounts:
    payload = effect.outcomes
    if not isinstance(payload, dict) or set(payload) != {"operations", "counts"}:
        raise MemoryError("Completed memory formation outcomes are invalid.")
    try:
        operations = [
            MemoryOperation.model_validate(operation)
            for operation in payload["operations"]
        ]
        counts = MemoryOutcomeCounts.model_validate(payload["counts"])
    except (TypeError, ValidationError):
        raise MemoryError("Completed memory formation outcomes are invalid.") from None
    if counts != MemoryOutcomeCounts.from_operations(operations):
        raise MemoryError("Completed memory formation outcomes are inconsistent.")
    return counts


def _position_json(
    created_at: datetime | None,
    message_id: UUID | None,
) -> dict[str, str] | None:
    if created_at is None and message_id is None:
        return None
    if created_at is None or message_id is None:
        raise MemoryError("Memory formation receipt has an incomplete watermark.")
    return {
        "created_at": created_at.isoformat(),
        "message_id": str(message_id),
    }


async def _continue_memory_backlog(job: MemoryFormationJobModel) -> None:
    """Best-effort file and spawn of the next immutable page after success."""
    successor: MemoryFormationJobModel | None = None
    try:
        scope = MemoryScope(
            organization_id=job.organization_id,
            level=MemoryLevel.CONVERSATION,
            owner_id=job.conversation_id,
        )
        async with start_transaction() as session:
            await _lock_cursor_key(session, scope)
            cursor = await session.scalar(
                select(MemoryFormationCursorModel)
                .where(
                    MemoryFormationCursorModel.organization_id == job.organization_id,
                    MemoryFormationCursorModel.conversation_id == job.conversation_id,
                    MemoryFormationCursorModel.active_job_id.is_(None),
                    MemoryFormationCursorModel.deleted.is_(False),
                )
                .with_for_update()
            )
            if cursor is not None and _cursor_has_backlog(cursor):
                successor = await _file_cursor_job(session, cursor)
        if successor is not None:
            await spawn_memory_formation(
                organization_id=successor.organization_id,
                job_id=successor.id,
            )
    except Exception as error:  # noqa: BLE001 - DB outbox/backlog remains durable
        logger.warning(
            "Could not continue memory formation backlog: %s",
            type(error).__name__,
        )


__all__ = [
    "MEMORY_FORMATION_WORKFLOW",
    "MemoryFormationWorkflow",
    "cancel_memory_formation",
    "enqueue_memory_formation",
    "register_memory_formation_workflow",
    "spawn_memory_formation",
    "spawn_unbound_memory_formations",
]
