"""Absurd workflow for storage-prefix discovery into ingestion jobs."""

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
from eylo.common.contracts.knowledgebase import KnowledgeScope
from eylo.common.database import start_transaction
from eylo.durable_runtime import (
    PlatformDurableRuntime,
    run_with_durable_heartbeat,
)
from eylo.events.schema.py_events.knowledgebase import KnowledgeWorkTransition
from eylo.modules.knowledgebase.events import register_corpus_lifecycle
from eylo.modules.knowledgebase.jobs import (
    MAX_CORPUS_OBJECTS,
    KnowledgeCorpusImportModel,
    storage_authority_from_record,
)
from eylo.modules.knowledgebase.services.corpus import CorpusImportService, screen
from eylo.modules.knowledgebase.services.ingestion import IngestionService
from eylo.modules.knowledgebase.services.knowledgebases import KnowledgebaseService
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.knowledgebase.durable_execution import (
    spawn_knowledge_ingestion,
)
from eylo.pipelines.knowledgebase.lifecycle import notify_cancelled_tasks
from eylo.pipelines.storage.runtime import resolve_storage_runtime_for_authority

logger = logging.getLogger(__name__)

KNOWLEDGE_CORPUS_WORKFLOW = "eylo.knowledge.corpus.v1"


def register_knowledge_corpus_workflow(runtime: PlatformDurableRuntime) -> None:
    workflow = KnowledgeCorpusWorkflow()
    runtime.register_task(
        name=KNOWLEDGE_CORPUS_WORKFLOW,
        handler=workflow.execute,
    )


async def spawn_knowledge_corpus(
    *,
    organization_id: UUID,
    import_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=KnowledgeCorpusImportModel,
        organization_id=organization_id,
        work_id=import_id,
        workflow_name=KNOWLEDGE_CORPUS_WORKFLOW,
        params_name="import_id",
        idempotency_prefix="knowledge-corpus",
    )


async def spawn_unbound_knowledge_corpora(*, limit: int = 100) -> int:
    async def spawn(organization_id: UUID, import_id: UUID) -> UUID:
        return await spawn_knowledge_corpus(
            organization_id=organization_id,
            import_id=import_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=KnowledgeCorpusImportModel,
        spawn=spawn,
        limit=limit,
    )
    for import_id, error in failures:
        logger.error(
            "Could not spawn knowledge corpus id=%s error_type=%s",
            import_id,
            type(error).__name__,
        )
    return spawned


async def cancel_knowledge_corpus(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
    import_id: UUID,
) -> bool:
    async with start_transaction() as session:
        cancelled, task_id = await CorpusImportService(session).cancel(
            import_id,
            knowledgebase_id,
            organization_id,
        )
    if cancelled and task_id is not None:
        await notify_cancelled_tasks(
            (task_id,),
            resource_kind="knowledge corpus",
            resource_id=import_id,
        )
    return cancelled


class KnowledgeCorpusWorkflow:
    """List a prefix, then atomically file child jobs and the import result."""

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, import_id = _parse_params(params)
        try:
            return await self._execute(
                organization_id=organization_id,
                import_id=import_id,
                task_context=task_context,
            )
        except CancelledTask:
            async with start_transaction() as session:
                work = AbsurdBoundWorkService(
                    KnowledgeCorpusImportModel,
                    session,
                )
                record = await work.get(
                    work_id=import_id,
                    organization_id=organization_id,
                    for_update=True,
                )
                changed, _task_id = await work.cancel(
                    work_id=import_id,
                    organization_id=organization_id,
                )
                if changed:
                    register_corpus_lifecycle(
                        record,
                        KnowledgeWorkTransition.CANCELLED,
                    )
            raise

    async def _execute(
        self,
        *,
        organization_id: UUID,
        import_id: UUID,
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        try:
            async with start_transaction() as session:
                record = await AbsurdBoundWorkService(
                    KnowledgeCorpusImportModel,
                    session,
                ).begin_attempt(
                    work_id=import_id,
                    organization_id=organization_id,
                )
                if record.state in {
                    DurableState.SUCCEEDED,
                    DurableState.FAILED,
                    DurableState.CANCELLED,
                }:
                    return _receipt(record)
                register_corpus_lifecycle(
                    record,
                    KnowledgeWorkTransition.ATTEMPT_STARTED,
                )
                knowledgebase = await KnowledgebaseService(session).get(
                    record.knowledgebase_id,
                    organization_id,
                )
                scope = KnowledgeScope(knowledgebase.scope)
                scope_id = knowledgebase.scope_id
                storage_authority = storage_authority_from_record(record)
                prefix = record.prefix
                knowledgebase_id = record.knowledgebase_id
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                import_id=import_id,
                error=error,
                permanent=isinstance(error, NotConfiguredError),
            )

        async def list_objects():
            async with start_transaction(ro=True) as session:
                storage = await resolve_storage_runtime_for_authority(
                    storage_authority,
                    db=session,
                )
            return await storage.adapter.list_objects(
                prefix,
                limit=MAX_CORPUS_OBJECTS,
            )

        try:
            objects = await run_with_durable_heartbeat(task_context, list_objects)
            keep, skipped = screen(objects)
        except Exception as error:  # noqa: BLE001 - listing failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                import_id=import_id,
                error=error,
                permanent=isinstance(error, NotConfiguredError),
            )

        queued_ids: list[UUID] = []
        async with start_transaction() as session:
            work = AbsurdBoundWorkService(KnowledgeCorpusImportModel, session)
            current = await work.get(
                work_id=import_id,
                organization_id=organization_id,
                for_update=True,
            )
            if current.state is not DurableState.RUNNING:
                return _receipt(current)
            ingestion = IngestionService(session)
            for entry in keep:
                job = await ingestion.enqueue_from_storage(
                    organization_id=organization_id,
                    knowledgebase_id=knowledgebase_id,
                    scope=scope,
                    scope_id=scope_id,
                    locator=storage_authority.locate(entry.key),
                    corpus_import_id=import_id,
                )
                if job is not None:
                    queued_ids.append(job.id)
            if current.state is DurableState.RUNNING:
                result = await work.succeed(
                    work_id=import_id,
                    organization_id=organization_id,
                    values={
                        "discovered_count": len(objects),
                        "queued_count": len(queued_ids),
                        "skipped": (
                            {"entries": skipped[:50], "total": len(skipped)}
                            if skipped
                            else None
                        ),
                    },
                )
                register_corpus_lifecycle(
                    result,
                    KnowledgeWorkTransition.SUCCEEDED,
                )
            else:
                result = current

        for job_id in queued_ids:
            try:
                await spawn_knowledge_ingestion(
                    organization_id=organization_id,
                    job_id=job_id,
                )
            except Exception as error:  # noqa: BLE001 - DB outbox retains the job
                logger.error(
                    "Could not immediately spawn ingestion id=%s error_type=%s",
                    job_id,
                    type(error).__name__,
                )
        return _receipt(result)


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "import_id"}:
        raise ValueError("Knowledge corpus task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["import_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Knowledge corpus task params contain an invalid UUID."
        ) from error


async def _handle_failure(
    *,
    organization_id: UUID,
    import_id: UUID,
    error: Exception,
    permanent: bool,
) -> dict[str, Any]:
    summary = (
        "knowledge_provider_not_configured"
        if isinstance(error, NotConfiguredError)
        else "knowledge_corpus_import_failed"
    )
    async with start_transaction() as session:
        work = AbsurdBoundWorkService(
            KnowledgeCorpusImportModel,
            session,
        )
        record = await work.get(
            work_id=import_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = record.state is DurableState.RUNNING
        state = await work.fail(
            work_id=import_id,
            organization_id=organization_id,
            error=summary,
            permanent=permanent,
        )
        if was_running:
            register_corpus_lifecycle(
                record,
                (
                    KnowledgeWorkTransition.RETRY_SCHEDULED
                    if state is DurableState.PENDING
                    else KnowledgeWorkTransition.FAILED
                ),
                failure_code=summary,
            )
    if state is DurableState.PENDING:
        raise error
    logger.warning("Knowledge corpus failed id=%s code=%s", import_id, summary)
    return {"import_id": str(import_id), "state": state.value}


def _receipt(record: KnowledgeCorpusImportModel) -> dict[str, Any]:
    return {
        "organization_id": str(record.organization_id),
        "import_id": str(record.id),
        "state": record.state.value,
        "discovered": record.discovered_count,
        "queued": record.queued_count,
    }


__all__ = [
    "KNOWLEDGE_CORPUS_WORKFLOW",
    "KnowledgeCorpusWorkflow",
    "cancel_knowledge_corpus",
    "register_knowledge_corpus_workflow",
    "spawn_knowledge_corpus",
    "spawn_unbound_knowledge_corpora",
]
