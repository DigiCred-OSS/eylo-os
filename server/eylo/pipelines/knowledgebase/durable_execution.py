"""Absurd workflow for one organization-owned knowledge ingestion job."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask

from eylo.absurd_work import (
    AbsurdBoundWorkService,
    DurableState,
    DurableWorkBindingPending,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.contracts.knowledgebase import (
    KnowledgeDocument,
    KnowledgebaseError,
)
from eylo.common.database import start_transaction
from eylo.durable_runtime import (
    PlatformDurableRuntime,
    run_with_durable_heartbeat,
)
from eylo.events.schema.py_events.knowledgebase import KnowledgeWorkTransition
from eylo.modules.knowledgebase.events import register_ingestion_lifecycle
from eylo.modules.knowledgebase.extraction import (
    DocumentExtractionError,
    extract_text,
)
from eylo.modules.knowledgebase.jobs import (
    MAX_STORAGE_OBJECT_BYTES,
    KnowledgeIngestionJobModel,
    storage_locator_from_job,
)
from eylo.modules.knowledgebase.services.ingestion import (
    IngestionError,
    IngestionService,
    document_from_job,
)
from eylo.modules.knowledgebase.services.knowledgebases import KnowledgebaseService
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.pipelines.knowledgebase.lifecycle import notify_cancelled_tasks
from eylo.pipelines.knowledgebase.resolver import resolve_adapter
from eylo.pipelines.storage.runtime import resolve_storage_runtime_for_authority

logger = logging.getLogger(__name__)

KNOWLEDGE_INGESTION_WORKFLOW = "eylo.knowledge.ingest.v1"


def register_knowledge_ingestion_workflow(
    runtime: PlatformDurableRuntime,
) -> None:
    """Register the document workflow on the process's shared DB runtime."""
    workflow = KnowledgeIngestionWorkflow()
    runtime.register_task(
        name=KNOWLEDGE_INGESTION_WORKFLOW,
        handler=workflow.execute,
    )


async def spawn_knowledge_ingestion(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> UUID:
    """Idempotently spawn and bind one committed product job."""
    return await spawn_bound_work(
        model=KnowledgeIngestionJobModel,
        organization_id=organization_id,
        work_id=job_id,
        workflow_name=KNOWLEDGE_INGESTION_WORKFLOW,
        params_name="job_id",
        idempotency_prefix="knowledge-ingestion",
    )


async def spawn_unbound_knowledge_ingestions(*, limit: int = 100) -> int:
    """DB-outbox recovery for producer callback loss; execution stays in Absurd."""

    async def spawn(organization_id: UUID, job_id: UUID) -> UUID:
        return await spawn_knowledge_ingestion(
            organization_id=organization_id,
            job_id=job_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=KnowledgeIngestionJobModel,
        spawn=spawn,
        limit=limit,
    )
    for job_id, error in failures:
        logger.error(
            "Could not spawn knowledge ingestion id=%s error_type=%s",
            job_id,
            type(error).__name__,
        )
    return spawned


async def cancel_knowledge_ingestion(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
    job_id: UUID,
) -> bool:
    """Commit product cancellation before notifying the exact engine task."""
    async with start_transaction() as session:
        service = IngestionService(session)
        cancelled, task_id = await service.cancel(
            job_id,
            knowledgebase_id,
            organization_id,
        )
        if cancelled:
            job = await service.get(job_id, knowledgebase_id, organization_id)
            await _file_ingestion_fact(
                session,
                job,
                "knowledge.ingestion.cancelled",
            )
    if cancelled and task_id is not None:
        await notify_cancelled_tasks(
            (task_id,),
            resource_kind="knowledge ingestion",
            resource_id=job_id,
        )
    return cancelled


class KnowledgeIngestionWorkflow:
    """Run an exact product row; no second claim/lease protocol participates."""

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
                work = AbsurdBoundWorkService(
                    KnowledgeIngestionJobModel,
                    session,
                )
                job = await work.get(
                    work_id=job_id,
                    organization_id=organization_id,
                    for_update=True,
                )
                changed, _task_id = await work.cancel(
                    work_id=job_id,
                    organization_id=organization_id,
                )
                if changed:
                    register_ingestion_lifecycle(
                        job,
                        KnowledgeWorkTransition.CANCELLED,
                    )
                    await _file_ingestion_fact(
                        session,
                        job,
                        "knowledge.ingestion.cancelled",
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
                    KnowledgeIngestionJobModel,
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
                register_ingestion_lifecycle(
                    job,
                    KnowledgeWorkTransition.ATTEMPT_STARTED,
                )
                await _file_ingestion_fact(
                    session,
                    job,
                    "knowledge.ingestion.started",
                )
                knowledgebase = await KnowledgebaseService(session).get(
                    job.knowledgebase_id,
                    organization_id,
                )
                adapter = await resolve_adapter(
                    knowledgebase,
                    organization_id=organization_id,
                    session=session,
                    embedding_authority=job,
                )
                expected_document_id = str(job.document_id)
                document = None if job.storage_key else document_from_job(job)
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        async def ingest() -> str:
            selected = document or await _fetch_document(job)
            return str(await adapter.ingest(selected))

        try:
            document_id = await task_context.step(
                f"knowledge-ingestion:{job_id}:ingest:v1",
                lambda: run_with_durable_heartbeat(task_context, ingest),
            )
        except Exception as error:  # noqa: BLE001 - work failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=error,
                permanent=_is_permanent(error),
            )

        if document_id != expected_document_id:
            return await _handle_failure(
                organization_id=organization_id,
                job_id=job_id,
                error=IngestionError(
                    f"Vendor stored document {document_id} but the job was filed "
                    f"under {expected_document_id}; the chunks are unreachable."
                ),
                permanent=True,
            )

        async with start_transaction() as session:
            work = AbsurdBoundWorkService(
                KnowledgeIngestionJobModel,
                session,
            )
            row = await work.get(
                work_id=job_id,
                organization_id=organization_id,
                for_update=True,
            )
            if row.state is DurableState.RUNNING:
                row = await work.succeed(
                    work_id=job_id,
                    organization_id=organization_id,
                )
                register_ingestion_lifecycle(
                    row,
                    KnowledgeWorkTransition.SUCCEEDED,
                )
                await _file_ingestion_fact(
                    session,
                    row,
                    "knowledge.ingestion.completed",
                )
        return _receipt(row, document_id=document_id)


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "job_id"}:
        raise ValueError("Knowledge ingestion task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["job_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Knowledge ingestion task params contain an invalid UUID."
        ) from error


async def _fetch_document(job: KnowledgeIngestionJobModel) -> KnowledgeDocument:
    locator = storage_locator_from_job(job)
    async with start_transaction(ro=True) as session:
        storage = await resolve_storage_runtime_for_authority(
            locator.authority,
            db=session,
        )
    raw = await storage.adapter.download_object(
        job.storage_key,
        max_bytes=MAX_STORAGE_OBJECT_BYTES,
    )
    if raw is None:
        raise IngestionError(
            f"Object '{job.storage_key}' is not in storage; it may have been "
            "moved or deleted since the import enumerated it."
        )
    return document_from_job(
        job,
        content=extract_text(job.storage_key, raw),
    )


async def _handle_failure(
    *,
    organization_id: UUID,
    job_id: UUID,
    error: Exception,
    permanent: bool,
) -> dict[str, Any]:
    summary = _failure_code(error)
    async with start_transaction() as session:
        work = AbsurdBoundWorkService(
            KnowledgeIngestionJobModel,
            session,
        )
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = job.state is DurableState.RUNNING
        state = await work.fail(
            work_id=job_id,
            organization_id=organization_id,
            error=summary,
            permanent=permanent,
        )
        if was_running:
            register_ingestion_lifecycle(
                job,
                (
                    KnowledgeWorkTransition.RETRY_SCHEDULED
                    if state is DurableState.PENDING
                    else KnowledgeWorkTransition.FAILED
                ),
                failure_code=summary,
            )
            if state is DurableState.FAILED:
                await _file_ingestion_fact(
                    session,
                    job,
                    "knowledge.ingestion.failed",
                    payload={"failure_code": summary},
                )
    if state is DurableState.PENDING:
        raise error
    logger.warning("Knowledge ingestion failed id=%s code=%s", job_id, summary)
    return {"job_id": str(job_id), "state": state.value}


async def _file_ingestion_fact(
    session,
    job: KnowledgeIngestionJobModel,
    event_type: str,
    *,
    payload: dict[str, str] | None = None,
) -> None:
    if job.user_session_id is None:
        return
    await file_user_session_fact(
        session,
        organization_id=job.organization_id,
        user_session_id=job.user_session_id,
        subject_type="knowledge.ingestion",
        subject_id=job.id,
        event_type=event_type,
        payload={
            "knowledgebase_id": str(job.knowledgebase_id),
            "document_id": str(job.document_id),
            **(payload or {}),
        },
    )


def _is_permanent(error: Exception) -> bool:
    return (
        isinstance(error, (DocumentExtractionError, NotConfiguredError))
        or isinstance(error, KnowledgebaseError)
        and not error.retryable
    )


def _failure_code(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "knowledge_provider_not_configured"
    if isinstance(error, DocumentExtractionError):
        return "knowledge_document_extraction_failed"
    if isinstance(error, IngestionError):
        return "knowledge_ingestion_invalid"
    if isinstance(error, KnowledgebaseError):
        return "knowledge_provider_failed"
    return "knowledge_ingestion_failed"


def _receipt(
    job: KnowledgeIngestionJobModel,
    *,
    document_id: str | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "organization_id": str(job.organization_id),
        "job_id": str(job.id),
        "state": job.state.value,
    }
    if document_id is not None:
        receipt["document_id"] = document_id
    return receipt


__all__ = [
    "KNOWLEDGE_INGESTION_WORKFLOW",
    "KnowledgeIngestionWorkflow",
    "cancel_knowledge_ingestion",
    "register_knowledge_ingestion_workflow",
    "spawn_knowledge_ingestion",
    "spawn_unbound_knowledge_ingestions",
]
