"""Absurd workflow for atomic Memory embedding-space cutover."""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask

from eylo.absurd_work import (
    DurableState,
    DurableWorkBindingPending,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.contracts.embedding import (
    EmbeddingError,
    target_embedding_space_from_record,
)
from eylo.common.contracts.memory import MemoryError
from eylo.common.database import start_transaction
from eylo.durable_runtime import PlatformDurableRuntime, run_with_durable_heartbeat
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.memory.models import MemoryReindexJobModel
from eylo.modules.memory.reindex_service import MemoryReindexService
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.resolver import resolve_pinned_embedding_runtime

logger = logging.getLogger(__name__)

MEMORY_REINDEX_WORKFLOW = "eylo.memory.reindex.v1"
_MAX_BATCHES_PER_ATTEMPT = 100


class MemoryReindexCatchUpPending(Exception):
    """Concurrent active-space writes must settle before atomic cutover."""


def register_memory_reindex_workflow(runtime: PlatformDurableRuntime) -> None:
    workflow = MemoryReindexWorkflow()
    runtime.register_task(name=MEMORY_REINDEX_WORKFLOW, handler=workflow.execute)


async def spawn_memory_reindex(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=MemoryReindexJobModel,
        organization_id=organization_id,
        work_id=job_id,
        workflow_name=MEMORY_REINDEX_WORKFLOW,
        params_name="job_id",
        idempotency_prefix="memory-reindex",
    )


async def spawn_unbound_memory_reindexes(*, limit: int = 100) -> int:
    async def spawn(organization_id: UUID, job_id: UUID) -> UUID:
        return await spawn_memory_reindex(
            organization_id=organization_id,
            job_id=job_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=MemoryReindexJobModel,
        spawn=spawn,
        limit=limit,
    )
    for job_id, error in failures:
        logger.error(
            "Could not spawn memory reindex id=%s error_type=%s",
            job_id,
            type(error).__name__,
        )
    return spawned


class MemoryReindexWorkflow:
    """Stage complete target vectors, then switch Memory in one transaction."""

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
            async with start_transaction() as session:
                await MemoryReindexService(session).cancel(
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
                job = await MemoryReindexService(session).begin_attempt(
                    organization_id=organization_id,
                    job_id=job_id,
                )
                if job.state in {
                    DurableState.SUCCEEDED,
                    DurableState.FAILED,
                    DurableState.CANCELLED,
                }:
                    return _receipt(job)
            async with start_transaction() as session:
                job = await MemoryReindexService(session).prepare_attempt(
                    organization_id=organization_id,
                    job_id=job_id,
                )
                target = target_embedding_space_from_record(job)
                if target is None:
                    raise MemoryError("Memory reindex target authority is missing.")
                runtime = await resolve_pinned_embedding_runtime(
                    organization_id,
                    provider_config_id=target.provider_config_id,
                    provider_config_revision=target.provider_config_revision,
                    db=session,
                )
                if not runtime.space.is_compatible_with(target):
                    raise MemoryError(
                        "Memory reindex execution does not match its target space."
                    )
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - projected product failure
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        try:
            for _ in range(_MAX_BATCHES_PER_ATTEMPT):
                async with start_transaction(ro=True) as session:
                    facts = await MemoryReindexService(session).next_batch(
                        organization_id=organization_id,
                        job_id=job_id,
                    )
                if not facts:
                    async with start_transaction() as session:
                        complete = await MemoryReindexService(
                            session
                        ).finalize_if_caught_up(
                            organization_id=organization_id,
                            job_id=job_id,
                        )
                    if complete:
                        async with start_transaction(ro=True) as session:
                            row = await MemoryReindexService(session).get_job(
                                organization_id=organization_id,
                                job_id=job_id,
                            )
                            return _receipt(row)
                    raise MemoryReindexCatchUpPending(
                        "Active Memory writes are still catching up."
                    )

                async def embed_batch() -> list[list[float]]:
                    return await runtime.embed_documents(
                        [fact.content for fact in facts]
                    )

                vectors = await task_context.step(
                    _step_name(job_id, [fact.id for fact in facts]),
                    lambda: run_with_durable_heartbeat(task_context, embed_batch),
                )
                async with start_transaction() as session:
                    await MemoryReindexService(session).store_vectors(
                        organization_id=organization_id,
                        job_id=job_id,
                        facts=facts,
                        vectors=vectors,
                    )
            raise MemoryReindexCatchUpPending(
                "Memory reindex batch window was exhausted before cutover."
            )
        except Exception as error:  # noqa: BLE001 - projected product failure
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )


async def _handle_failure(
    *,
    organization_id: UUID,
    job_id: UUID,
    error: Exception,
    permanent: bool,
) -> dict[str, Any]:
    async with start_transaction() as session:
        state = await MemoryReindexService(session).record_failure(
            organization_id=organization_id,
            job_id=job_id,
            error=error,
            permanent=permanent,
        )
    if state is DurableState.PENDING:
        raise error
    logger.warning(
        "Memory reindex failed id=%s error_type=%s",
        job_id,
        type(error).__name__,
    )
    return {"job_id": str(job_id), "state": state.value}


def _is_permanent(error: Exception) -> bool:
    if isinstance(error, (InvalidEmbeddingConfig, NotConfiguredError)):
        return True
    if isinstance(error, EmbeddingError):
        return not error.retryable
    if isinstance(error, MemoryReindexCatchUpPending):
        return False
    if isinstance(error, MemoryError):
        return not error.retryable
    return False


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "job_id"}:
        raise ValueError("Memory reindex task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["job_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError("Memory reindex task params contain an invalid UUID.") from error


def _step_name(job_id: UUID, fact_ids: list[UUID]) -> str:
    digest = hashlib.sha256(
        ",".join(str(fact_id) for fact_id in fact_ids).encode("ascii")
    ).hexdigest()[:16]
    return f"memory-reindex:{job_id}:facts:{digest}:v1"


def _receipt(job: MemoryReindexJobModel) -> dict[str, Any]:
    return {
        "organization_id": str(job.organization_id),
        "job_id": str(job.id),
        "state": job.state.value,
        "source_fact_count": job.source_fact_count,
        "indexed_fact_count": job.indexed_fact_count,
    }


__all__ = [
    "MEMORY_REINDEX_WORKFLOW",
    "MemoryReindexWorkflow",
    "register_memory_reindex_workflow",
    "spawn_memory_reindex",
    "spawn_unbound_memory_reindexes",
]
