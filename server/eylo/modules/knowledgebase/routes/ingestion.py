"""Operator routes for ingestion jobs.

Submitting returns a job, not a result. Ingestion takes a variable amount of
time and can fail, so an endpoint that blocked until it finished would be
claiming a certainty it does not have — and would hold a request open across a
worker restart that the job itself survives.

The status endpoint is the other half of that bargain. Handing back a job id
and providing no way to ask about it would make "accepted" indistinguishable
from "lost".
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.contracts.knowledgebase import KnowledgeDocument, KnowledgeScope
from eylo.common.database import get_transaction, start_transaction
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.knowledgebase.jobs import IngestionState
from eylo.modules.knowledgebase.schemas import (
    CorpusImportRead,
    CorpusImportRequest,
    IngestRequest,
    IngestionJobRead,
)
from eylo.modules.knowledgebase.services.corpus import (
    CorpusImportError,
    CorpusImportService,
)
from eylo.modules.knowledgebase.services.ingestion import (
    IngestionError,
    IngestionService,
)
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.pipelines.storage.runtime import resolve_storage_runtime_for_new

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions",
    tags=[APP_TAG],
)


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


async def _require_knowledgebase(
    session,
    knowledgebase_id: UUID,
    organization_id: UUID,
):
    try:
        return await KnowledgebaseService(session).get(
            knowledgebase_id,
            organization_id,
        )
    except KnowledgebaseError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestionJobRead)
async def submit_ingestion(
    organization_id: UUID,
    knowledgebase_id: UUID,
    request: IngestRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Queue a document. 202, because the work has not happened yet.

    Idempotent on the document's identity: submitting the same document while
    a job for it is still pending or running returns that job rather than
    queueing a second one.
    """
    _authorize(organization_id, current_user)
    async with start_transaction():
        session = get_transaction()
        knowledgebase = await _require_knowledgebase(
            session,
            knowledgebase_id,
            organization_id,
        )

        document = KnowledgeDocument(
            content=request.content,
            # From the knowledgebase, never from the request. A caller who
            # could name a scope could file a document somewhere it would be
            # read by agents that were never meant to see it.
            scope=KnowledgeScope(knowledgebase.scope),
            scope_id=knowledgebase.scope_id,
            title=request.title,
            source_uri=request.source_uri,
            metadata=request.metadata or {},
        )
        try:
            job = await IngestionService(session).enqueue(
                organization_id=organization_id,
                knowledgebase_id=knowledgebase_id,
                document=document,
            )
        except IngestionError as error:
            raise HTTPException(status_code=400, detail=str(error))
        response = IngestionJobRead.model_validate(job)

    # After the commit, deliberately. A nudge for a job that no longer exists
    # because the transaction rolled back would have a worker scanning for
    # nothing; a job with no nudge is picked up by the sweeper within a minute.
    from eylo.pipelines.knowledgebase.durable_execution import (
        spawn_knowledge_ingestion,
    )

    try:
        await spawn_knowledge_ingestion(
            organization_id=organization_id,
            job_id=response.id,
        )
    except Exception as error:  # noqa: BLE001 - DB outbox remains recoverable
        logger.error(
            "Could not immediately spawn ingestion id=%s error_type=%s",
            response.id,
            type(error).__name__,
        )
    return response


@router.get("", response_model=list[IngestionJobRead])
async def list_ingestions(
    organization_id: UUID,
    knowledgebase_id: UUID,
    state: IngestionState | None = None,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Recent jobs for this knowledgebase, newest first."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        session = get_transaction()
        await _require_knowledgebase(session, knowledgebase_id, organization_id)
        return await IngestionService(session).list_for_knowledgebase(
            knowledgebase_id, organization_id, states=[state] if state else None
        )


# ---------------------------------------------------------------------------
# Corpus routes are declared before the `/{job_id}` routes, and must stay that
# way. FastAPI matches in declaration order, so `/{job_id}` — a path parameter
# that accepts any single segment — swallows `/corpus` if it comes first, and
# every corpus listing 422s on "corpus is not a valid UUID". Nothing about the
# code reads as wrong; the routes simply stop existing.
# ---------------------------------------------------------------------------


@router.post(
    "/corpus", status_code=status.HTTP_202_ACCEPTED, response_model=CorpusImportRead
)
async def start_corpus_import(
    organization_id: UUID,
    knowledgebase_id: UUID,
    request: CorpusImportRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Sweep a storage prefix into this knowledgebase.

    Returns immediately with an import to watch. The sweep enumerates the
    prefix and files one ingestion job per object; nothing is read until a
    worker picks each job up.

    **Safe to re-run.** Each object's identity is its storage address, so a
    second import replaces changed documents and skips unchanged ones rather
    than growing a second copy of the corpus. That is also what makes a crashed
    sweep recoverable — it is simply run again.
    """
    _authorize(organization_id, current_user)
    async with start_transaction():
        session = get_transaction()
        await _require_knowledgebase(session, knowledgebase_id, organization_id)
        storage = await resolve_storage_runtime_for_new(
            organization_id,
            provider_config_id=request.storage_provider_config_id,
            db=session,
        )
        record = await CorpusImportService(session).create(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            prefix=request.prefix,
            storage_authority=storage.authority,
        )
        response = CorpusImportRead.model_validate(record)

    from eylo.pipelines.knowledgebase.corpus_durable_execution import (
        spawn_knowledge_corpus,
    )

    try:
        await spawn_knowledge_corpus(
            organization_id=organization_id,
            import_id=response.id,
        )
    except Exception as error:  # noqa: BLE001 - DB outbox remains recoverable
        logger.error(
            "Could not immediately spawn corpus import id=%s error_type=%s",
            response.id,
            type(error).__name__,
        )
    return response


@router.get("/corpus", response_model=list[CorpusImportRead])
async def list_corpus_imports(
    organization_id: UUID,
    knowledgebase_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        session = get_transaction()
        await _require_knowledgebase(session, knowledgebase_id, organization_id)
        return await CorpusImportService(session).list_for_knowledgebase(
            knowledgebase_id, organization_id
        )


@router.get("/corpus/{import_id}", response_model=CorpusImportRead)
async def get_corpus_import(
    organization_id: UUID,
    knowledgebase_id: UUID,
    import_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """One import, including what it skipped and why."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        try:
            return await CorpusImportService(get_transaction()).get(
                import_id,
                knowledgebase_id,
                organization_id,
            )
        except CorpusImportError as error:
            raise HTTPException(status_code=404, detail=str(error))


@router.post("/corpus/{import_id}/cancel", response_model=CorpusImportRead)
async def cancel_corpus_import(
    organization_id: UUID,
    knowledgebase_id: UUID,
    import_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Stop a sweep. Jobs it already filed keep running.

    Cancelling the sweep does not cancel the documents it found — those are
    real work already accepted. Cancel them individually if that is what you
    want.
    """
    _authorize(organization_id, current_user)
    from eylo.pipelines.knowledgebase.corpus_durable_execution import (
        cancel_knowledge_corpus,
    )

    try:
        cancelled = await cancel_knowledge_corpus(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            import_id=import_id,
        )
    except CorpusImportError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail="That import is not cancellable; it has already finished.",
        )
    async with start_transaction(ro=True):
        try:
            return await CorpusImportService(get_transaction()).get(
                import_id,
                knowledgebase_id,
                organization_id,
            )
        except CorpusImportError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{job_id}", response_model=IngestionJobRead)
async def get_ingestion(
    organization_id: UUID,
    knowledgebase_id: UUID,
    job_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        try:
            return await IngestionService(get_transaction()).get(
                job_id,
                knowledgebase_id,
                organization_id,
            )
        except IngestionError as error:
            raise HTTPException(status_code=404, detail=str(error))


@router.post("/{job_id}/cancel", response_model=IngestionJobRead)
async def cancel_ingestion(
    organization_id: UUID,
    knowledgebase_id: UUID,
    job_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Stop a job that has not finished.

    A running job may still complete the document it is on — cancelling stops
    the job, not the write in flight. Promising otherwise would be a guarantee
    this cannot keep, and the write is idempotent either way.
    """
    _authorize(organization_id, current_user)
    from eylo.pipelines.knowledgebase.durable_execution import (
        cancel_knowledge_ingestion,
    )

    try:
        cancelled = await cancel_knowledge_ingestion(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            job_id=job_id,
        )
    except IngestionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail="That job is not cancellable; it has already finished.",
        )
    async with start_transaction(ro=True):
        try:
            return await IngestionService(get_transaction()).get(
                job_id,
                knowledgebase_id,
                organization_id,
            )
        except IngestionError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
