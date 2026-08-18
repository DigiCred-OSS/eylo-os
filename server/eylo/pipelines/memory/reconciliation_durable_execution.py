"""Absurd-owned execution for bounded Memory reconciliation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import (
    DurableState,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.contracts.embedding import embedding_space_from_record
from eylo.common.contracts.memory import MemoryError, MemoryLevel, MemoryScope
from eylo.common.contracts.memory_reconciliation import (
    MEMORY_RECONCILIATION_MAX_CANDIDATES,
    MemoryReconciliationBatch,
    MemoryReconciliationCandidate,
    MemoryReconciliationInput,
    MemoryReconciliationProposal,
)
from eylo.common.database import start_transaction
from eylo.durable_runtime import (
    PlatformDurableRuntime,
    run_with_durable_heartbeat,
)
from eylo.modules.agent_runs.budgets import (
    activate_memory_reconciliation_reservation_in_transaction,
    check_memory_reconciliation_active_time,
    memory_reconciliation_execution_budget_scope,
    release_memory_reconciliation_reservation_in_transaction,
    require_memory_reconciliation_usage_reported,
    reserve_memory_reconciliation_in_transaction,
)
from eylo.modules.agent_runs.domain import (
    ExecutionBudgetDimension,
    ExecutionBudgetError,
    ExecutionBudgetExceeded,
    ExecutionBudgetNotConfigured,
    ExecutionBudgetUnavailable,
    ExecutionUsageNotReported,
)
from eylo.modules.memory.models import (
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationJobModel,
)
from eylo.modules.memory.reconciliation_service import (
    MemoryReconciliationService,
    MemoryReconciliationStale,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.memory.resolver import resolve_memory_runtime
from eylo.sockets.memory.reconciliation import (
    RECONCILIATION_PROMPT_REVISION,
    RECONCILIATION_SYSTEM_PROMPT,
    build_reconciliation_prompt,
    parse_reconciliation_proposal,
)

logger = logging.getLogger(__name__)

MEMORY_RECONCILIATION_WORKFLOW = "eylo.memory.reconcile.v1"


def register_memory_reconciliation_workflow(runtime: PlatformDurableRuntime) -> None:
    workflow = MemoryReconciliationWorkflow()
    runtime.register_task(
        name=MEMORY_RECONCILIATION_WORKFLOW,
        handler=workflow.execute,
    )


async def file_memory_reconciliation_backlog(*, limit: int = 100) -> int:
    async with start_transaction(ro=True) as session:
        cursor_ids = await MemoryReconciliationService(
            session
        ).backlog_cursor_ids(limit=limit)
    filed = 0
    for cursor_id in cursor_ids:
        try:
            async with start_transaction() as session:
                job = await _file_next_with_budget(session, cursor_id)
                if job is not None:
                    filed += 1
        except Exception as error:  # noqa: BLE001 - DB outbox stays retryable
            logger.warning(
                "Could not file Memory reconciliation cursor: %s",
                type(error).__name__,
            )
    return filed


async def spawn_memory_reconciliation(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=MemoryReconciliationJobModel,
        organization_id=organization_id,
        work_id=job_id,
        workflow_name=MEMORY_RECONCILIATION_WORKFLOW,
        params_name="job_id",
        idempotency_prefix="memory-reconciliation",
    )


async def spawn_unbound_memory_reconciliations(*, limit: int = 100) -> int:
    await file_memory_reconciliation_backlog(limit=limit)

    async def spawn(organization_id: UUID, job_id: UUID) -> UUID:
        return await spawn_memory_reconciliation(
            organization_id=organization_id,
            job_id=job_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=MemoryReconciliationJobModel,
        spawn=spawn,
        limit=limit,
    )
    for job_id, error in failures:
        logger.error(
            "Memory reconciliation %s could not bind to Absurd: %s",
            job_id,
            type(error).__name__,
        )
    return spawned


async def _file_next_with_budget(
    session: AsyncSession,
    cursor_id: UUID,
) -> MemoryReconciliationJobModel | None:
    job = await MemoryReconciliationService(session).file_next(cursor_id)
    if job is not None:
        await reserve_memory_reconciliation_in_transaction(
            session,
            organization_id=job.organization_id,
            job_id=job.id,
        )
    return job


class MemoryReconciliationWorkflow:
    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, job_id = _parse_params(params)
        try:
            async with start_transaction() as session:
                job = await MemoryReconciliationService(session).begin_attempt(
                    organization_id=organization_id,
                    job_id=job_id,
                )
                if _terminal(job):
                    return _receipt(job)

            async with start_transaction() as session:
                service = MemoryReconciliationService(session)
                job = await service.running_job(
                    organization_id=organization_id,
                    job_id=job_id,
                )
                if _terminal(job):
                    return _receipt(job)
                await activate_memory_reconciliation_reservation_in_transaction(
                    session,
                    organization_id=organization_id,
                    job_id=job_id,
                )
                embedding_space = embedding_space_from_record(job)
                if embedding_space is None:
                    raise MemoryError(
                        "Memory reconciliation job has no embedding authority."
                    )
                runtime = await resolve_memory_runtime(
                    organization_id,
                    session,
                    provider_config_id=job.memory_provider_config_id,
                    provider_config_revision=job.memory_provider_config_revision,
                    embedding_space=embedding_space,
                )
                _validate_runtime_authority(job, runtime)
        except Exception as error:  # noqa: BLE001 - persisted failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
            )

        try:
            batch = await _load_or_build_batch(job, runtime)
            remaining_milliseconds = await check_memory_reconciliation_active_time(
                organization_id=organization_id,
                job_id=job_id,
            )
            if remaining_milliseconds <= 0:
                raise ExecutionBudgetExceeded(ExecutionBudgetDimension.ACTIVE_TIME)
            try:
                async with asyncio.timeout(remaining_milliseconds / 1_000):
                    proposal = await _load_or_propose(
                        job,
                        runtime,
                        batch,
                        task_context,
                    )
            except TimeoutError:
                raise ExecutionBudgetExceeded(
                    ExecutionBudgetDimension.ACTIVE_TIME
                ) from None
            if batch.inputs:
                await require_memory_reconciliation_usage_reported(
                    organization_id=organization_id,
                    job_id=job_id,
                )
            async with start_transaction() as session:
                exceeded = (
                    await release_memory_reconciliation_reservation_in_transaction(
                        session,
                        organization_id=organization_id,
                        job_id=job_id,
                    )
                )
                if exceeded is not None:
                    raise ExecutionBudgetExceeded(exceeded)
                row = await MemoryReconciliationService(session).apply(
                    organization_id=organization_id,
                    job_id=job_id,
                    batch=batch,
                    proposal=proposal,
                )
                receipt = _receipt(row)
        except Exception as error:  # noqa: BLE001 - persisted failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
            )

        if row.state is DurableState.SUCCEEDED:
            await _continue_backlog(row)
        return receipt


async def _load_or_build_batch(job, runtime) -> MemoryReconciliationBatch:
    async with start_transaction(ro=True) as session:
        service = MemoryReconciliationService(session)
        stored = await service.load_batch(
            organization_id=job.organization_id,
            job_id=job.id,
        )
        if stored is not None:
            return stored
        changes = await service.changes_for_job(job)
        skeleton = await service.build_batch_skeleton(job, changes)

    batch = await _with_candidates(job, runtime, skeleton)
    async with start_transaction() as session:
        await MemoryReconciliationService(session).store_batch(
            organization_id=job.organization_id,
            job_id=job.id,
            batch=batch,
        )
    return batch


async def _with_candidates(job, runtime, batch) -> MemoryReconciliationBatch:
    if not batch.inputs:
        return batch
    scope = MemoryScope(
        organization_id=job.organization_id,
        level=MemoryLevel(job.scope_level),
        owner_id=job.owner_id,
    )
    ordered_ids: dict[UUID, list[UUID]] = {}
    all_ids: set[UUID] = set()
    for item in batch.inputs:
        results = await runtime.adapter.search(
            item.content,
            scopes=(scope,),
            limit=MEMORY_RECONCILIATION_MAX_CANDIDATES + 1,
        )
        candidate_ids: list[UUID] = []
        for result in results:
            if result.id == item.memory_id or result.id in candidate_ids:
                continue
            candidate_ids.append(result.id)
            if len(candidate_ids) == MEMORY_RECONCILIATION_MAX_CANDIDATES:
                break
        ordered_ids[item.memory_id] = candidate_ids
        all_ids.update(candidate_ids)

    rows: list[MemoryModel] = []
    if all_ids:
        async with start_transaction(ro=True) as session:
            rows = list(
                (
                    await session.scalars(
                        select(MemoryModel).where(
                            MemoryModel.organization_id == job.organization_id,
                            MemoryModel.memory_provider_config_id
                            == job.memory_provider_config_id,
                            MemoryModel.embedding_space_id == job.embedding_space_id,
                            MemoryModel.id.in_(all_ids),
                                MemoryModel.deleted.is_(False),
                                or_(
                                    MemoryModel.expires_at.is_(None),
                                    MemoryModel.expires_at > func.now(),
                                ),
                        )
                    )
                ).all()
            )
    by_id = {
        row.id: row for row in rows if _matches_job_scope(row, job)
    }
    enriched: list[MemoryReconciliationInput] = []
    for item in batch.inputs:
        candidates = tuple(
            MemoryReconciliationCandidate(
                memory_id=row.id,
                state_revision=row.state_revision,
                content=row.content,
            )
            for candidate_id in ordered_ids[item.memory_id]
            if (row := by_id.get(candidate_id)) is not None
        )
        enriched.append(item.model_copy(update={"candidates": candidates}))
    return batch.model_copy(update={"inputs": tuple(enriched)})


async def _load_or_propose(
    job,
    runtime,
    batch: MemoryReconciliationBatch,
    task_context: AsyncTaskContext,
) -> MemoryReconciliationProposal:
    async with start_transaction(ro=True) as session:
        stored = await MemoryReconciliationService(session).load_proposal(
            organization_id=job.organization_id,
            job_id=job.id,
        )
    if stored is not None:
        return stored

    if not batch.inputs:
        proposal = MemoryReconciliationProposal(decisions=())
    else:

        async def complete() -> str:
            with memory_reconciliation_execution_budget_scope(
                organization_id=job.organization_id,
                job_id=job.id,
            ):
                return await runtime.reconciliation_completer(
                    system=RECONCILIATION_SYSTEM_PROMPT,
                    user=build_reconciliation_prompt(batch.inputs),
                )

        raw = await task_context.step(
            f"memory-reconciliation:{job.id}:propose:v1",
            lambda: run_with_durable_heartbeat(task_context, complete),
        )
        proposal = parse_reconciliation_proposal(raw, batch.inputs)

    async with start_transaction() as session:
        await MemoryReconciliationService(session).store_proposal(
            organization_id=job.organization_id,
            job_id=job.id,
            proposal=proposal,
        )
    return proposal


async def _handle_failure(
    *,
    organization_id: UUID,
    job_id: UUID,
    error: Exception,
) -> dict[str, Any]:
    summary = _safe_failure_summary(error)
    if isinstance(error, MemoryReconciliationStale):
        async with start_transaction() as session:
            row, cursor_id = await MemoryReconciliationService(
                session
            ).abandon_stale(
                organization_id=organization_id,
                job_id=job_id,
                error=summary,
            )
            await release_memory_reconciliation_reservation_in_transaction(
                session,
                organization_id=organization_id,
                job_id=job_id,
            )
            receipt = _receipt(row)
        await _refile_and_spawn(cursor_id)
        return receipt
    async with start_transaction() as session:
        row = await MemoryReconciliationService(session).fail(
            organization_id=organization_id,
            job_id=job_id,
            error=summary,
            permanent=_is_permanent(error),
        )
        await release_memory_reconciliation_reservation_in_transaction(
            session,
            organization_id=organization_id,
            job_id=job_id,
        )
        receipt = _receipt(row)
    if row.state is DurableState.PENDING:
        raise MemoryError(
            "Memory reconciliation retry requested.",
            retryable=True,
        ) from None
    if row.state is DurableState.FAILED:
        logger.warning("Memory reconciliation %s failed: %s", job_id, summary)
    return receipt


async def _refile_and_spawn(cursor_id: UUID) -> None:
    successor: MemoryReconciliationJobModel | None = None
    try:
        async with start_transaction() as session:
            successor = await _file_next_with_budget(session, cursor_id)
        if successor is not None:
            await spawn_memory_reconciliation(
                organization_id=successor.organization_id,
                job_id=successor.id,
            )
    except Exception as error:  # noqa: BLE001 - periodic nudge recovers the outbox
        logger.warning(
            "Could not re-file stale Memory reconciliation: %s",
            type(error).__name__,
        )


async def _continue_backlog(job: MemoryReconciliationJobModel) -> None:
    successor: MemoryReconciliationJobModel | None = None
    try:
        async with start_transaction() as session:
            cursor_id = await session.scalar(
                select(MemoryReconciliationCursorModel.id).where(
                    MemoryReconciliationCursorModel.organization_id
                    == job.organization_id,
                    MemoryReconciliationCursorModel.memory_provider_config_id
                    == job.memory_provider_config_id,
                    MemoryReconciliationCursorModel.scope_level == job.scope_level,
                    MemoryReconciliationCursorModel.owner_id == job.owner_id,
                    MemoryReconciliationCursorModel.active_job_id.is_(None),
                    MemoryReconciliationCursorModel.deleted.is_(False),
                )
            )
            if cursor_id is not None:
                successor = await _file_next_with_budget(session, cursor_id)
        if successor is not None:
            await spawn_memory_reconciliation(
                organization_id=successor.organization_id,
                job_id=successor.id,
            )
    except Exception as error:  # noqa: BLE001 - periodic nudge recovers the outbox
        logger.warning(
            "Could not continue Memory reconciliation backlog: %s",
            type(error).__name__,
        )

def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "job_id"}:
        raise ValueError("Memory reconciliation task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["job_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Memory reconciliation task params contain an invalid UUID."
        ) from error


def _validate_runtime_authority(job, runtime) -> None:
    authority = runtime.extraction_authority
    if (
        authority.provider_config_id != job.reconciliation_llm_provider_config_id
        or authority.provider_config_revision
        != job.reconciliation_llm_provider_config_revision
        or authority.provider != job.reconciliation_llm_provider
        or authority.model != job.reconciliation_llm_model
        or job.reconciliation_prompt_revision != RECONCILIATION_PROMPT_REVISION
    ):
        raise MemoryError("Memory reconciliation authority changed before execution.")


def _terminal(job: MemoryReconciliationJobModel) -> bool:
    return job.state in {
        DurableState.SUCCEEDED,
        DurableState.FAILED,
        DurableState.CANCELLED,
    }


def _receipt(job: MemoryReconciliationJobModel) -> dict[str, Any]:
    return {
        "organization_id": str(job.organization_id),
        "job_id": str(job.id),
        "state": job.state.value,
        "generation": job.generation,
        "change_count": job.change_count,
        "outcomes": {
            "considered": job.considered_count,
            "duplicate": job.duplicate_count,
            "superseded": job.superseded_count,
            "conflict": job.conflict_count,
            "unrelated": job.unrelated_count,
            "failed": job.failed_count,
        },
    }


def _safe_failure_summary(error: Exception) -> str:
    if isinstance(error, MemoryReconciliationStale):
        return "memory_reconciliation_snapshot_stale"
    if isinstance(error, NotConfiguredError):
        return "memory_reconciliation_dependency_not_configured"
    if isinstance(error, ExecutionBudgetNotConfigured):
        return "memory_reconciliation_execution_budget_not_configured"
    if isinstance(error, ExecutionBudgetUnavailable):
        return (
            f"memory_reconciliation_execution_capacity_"
            f"{error.dimension.value}_unavailable"
        )
    if isinstance(error, ExecutionBudgetExceeded):
        return (
            f"memory_reconciliation_execution_{error.dimension.value}_limit_exceeded"
        )
    if isinstance(error, ExecutionUsageNotReported):
        return "memory_reconciliation_execution_usage_not_reported"
    if isinstance(error, ExecutionBudgetError):
        return "memory_reconciliation_execution_budget_conflict"
    if isinstance(error, MemoryError):
        return (
            "memory_reconciliation_retryable_failure"
            if error.retryable
            else "memory_reconciliation_contract_failure"
        )
    return "memory_reconciliation_internal_failure"


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


def _matches_job_scope(fact: MemoryModel, job) -> bool:
    level = MemoryLevel(job.scope_level)
    owner_id = {
        MemoryLevel.AGENT: fact.agent_id,
        MemoryLevel.USER: fact.contact_id,
        MemoryLevel.CONVERSATION: fact.conversation_id,
    }[level]
    return MemoryLevel(fact.scope_level) is level and owner_id == job.owner_id

__all__ = [
    "MEMORY_RECONCILIATION_WORKFLOW",
    "MemoryReconciliationWorkflow",
    "file_memory_reconciliation_backlog",
    "register_memory_reconciliation_workflow",
    "spawn_memory_reconciliation",
    "spawn_unbound_memory_reconciliations",
]
