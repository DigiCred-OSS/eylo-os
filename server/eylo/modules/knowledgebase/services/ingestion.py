"""Driving the ingestion state machine.

Every transition here is a single SQL statement with the old state in its
WHERE clause. That is not stylistic — it is what makes each one safe against a
second worker doing the same thing at the same moment. A read-then-write would
let two workers both see PENDING and both claim; an UPDATE that names the state
it expects lets exactly one win, and the loser learns it lost from the row
count.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import AbsurdBoundWorkService
from eylo.common.contracts.embedding import (
    EmbeddingSpace,
    embedding_space_from_record,
)
from eylo.common.contracts.knowledgebase import (
    MAX_KNOWLEDGE_METADATA_BYTES,
    KnowledgeDocument,
    KnowledgeScope,
    derive_document_id,
    derive_identity,
)
from eylo.common.contracts.storage import StorageLocator
from eylo.durable_runtime import DURABLE_MAX_ATTEMPTS
from eylo.events.schema.py_events.knowledgebase import KnowledgeWorkTransition
from eylo.modules.knowledgebase.events import register_ingestion_lifecycle
from eylo.modules.knowledgebase.jobs import (
    MAX_CONTENT_BYTES,
    IngestionState,
    KnowledgeIngestionJobModel,
)
from eylo.modules.knowledgebase.models import KnowledgebaseModel

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """A job could not be enqueued or transitioned."""


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- enqueue -----------------------------------------------------

    async def enqueue(
        self,
        *,
        organization_id: UUID,
        knowledgebase_id: UUID,
        document: KnowledgeDocument,
        user_session_id: UUID | None = None,
        max_attempts: int = DURABLE_MAX_ATTEMPTS,
    ) -> KnowledgeIngestionJobModel:
        """Record a document to be ingested, or return the job already doing it."""
        if not document.content.strip():
            raise IngestionError("Refusing to enqueue an empty document.")

        size = len(document.content.encode("utf-8"))
        if size > MAX_CONTENT_BYTES:
            # Refused rather than truncated. A silently shortened document is
            # a knowledgebase that answers confidently from the first half of
            # a policy, and nothing downstream can tell.
            raise IngestionError(
                f"Document is {size} bytes; the inline limit is "
                f"{MAX_CONTENT_BYTES}. Split it or ingest it from a source."
            )

        try:
            metadata_size = len(
                json.dumps(document.metadata, separators=(",", ":")).encode("utf-8")
            )
        except (TypeError, ValueError):
            raise IngestionError("Document metadata must be valid JSON.") from None
        if metadata_size > MAX_KNOWLEDGE_METADATA_BYTES:
            raise IngestionError(
                "Document metadata exceeds the "
                f"{MAX_KNOWLEDGE_METADATA_BYTES} byte limit."
            )

        embedding_space = await self._require_target(
            knowledgebase_id,
            organization_id,
            scope=document.scope,
            scope_id=document.scope_id,
        )
        document_id = UUID(document.document_id)
        existing = await self._find_active(
            organization_id,
            knowledgebase_id,
            document_id,
        )
        if existing is not None:
            logger.info(
                "Ingestion for %s is already %s; returning job %s.",
                document.identity, existing.state.value, existing.id,
            )
            return existing

        job = KnowledgeIngestionJobModel(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            user_session_id=user_session_id,
            document_key=document.identity,
            document_id=document_id,
            scope=document.scope.value,
            scope_id=document.scope_id,
            content=document.content,
            title=document.title,
            source_uri=document.source_uri,
            meta=document.metadata or None,
            state=IngestionState.PENDING,
            max_attempts=max_attempts,
            **_embedding_job_fields(embedding_space),
        )
        try:
            # A savepoint, not a plain flush. The partial unique index catches
            # a race the check above cannot — two enqueues can both read
            # nothing and both try to insert — but recovering from that must
            # not cost the caller their transaction. A bare `rollback()` here
            # would discard whatever else the request had already written.
            async with self.session.begin_nested():
                self.session.add(job)
                await self.session.flush()
        except IntegrityError:
            winner = await self._find_active(
                organization_id,
                knowledgebase_id,
                document_id,
            )
            if winner is None:
                raise
            logger.info(
                "Lost the enqueue race for %s; job %s owns it.",
                document.identity, winner.id,
            )
            return winner
        register_ingestion_lifecycle(job, KnowledgeWorkTransition.QUEUED)
        return job

    async def enqueue_from_storage(
        self,
        *,
        organization_id: UUID,
        knowledgebase_id: UUID,
        scope: KnowledgeScope,
        scope_id: str,
        locator: StorageLocator,
        corpus_import_id: UUID | None = None,
        max_attempts: int = DURABLE_MAX_ATTEMPTS,
    ) -> KnowledgeIngestionJobModel | None:
        """File a job for an object in storage, without reading it."""
        if str(locator.authority.organization_id) != str(organization_id):
            raise IngestionError(
                "Storage locator must belong to the ingestion organization."
            )
        embedding_space = await self._require_target(
            knowledgebase_id,
            organization_id,
            scope=scope,
            scope_id=scope_id,
        )
        source_uri = locator.uri
        identity = derive_identity(scope, scope_id, source_uri=source_uri)
        document_id = UUID(derive_document_id(identity))

        if (
            await self._find_active(
                organization_id,
                knowledgebase_id,
                document_id,
            )
            is not None
        ):
            return None

        job = KnowledgeIngestionJobModel(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            document_key=identity,
            document_id=document_id,
            scope=scope.value,
            scope_id=scope_id,
            content=None,
            storage_key=locator.key,
            storage_provider_config_id=locator.authority.provider_config_id,
            storage_provider_config_revision=(
                locator.authority.provider_config_revision
            ),
            storage_provider=locator.authority.provider,
            storage_authority=dict(locator.authority.location),
            source_uri=source_uri,
            corpus_import_id=corpus_import_id,
            state=IngestionState.PENDING,
            max_attempts=max_attempts,
            **_embedding_job_fields(embedding_space),
        )
        try:
            async with self.session.begin_nested():
                self.session.add(job)
                await self.session.flush()
        except IntegrityError:
            # Another sweep filed it between the check and the insert. Nothing
            # to do — the job exists and will run.
            return None
        register_ingestion_lifecycle(job, KnowledgeWorkTransition.QUEUED)
        return job

    async def cancel(
        self,
        job_id: UUID,
        knowledgebase_id: UUID,
        organization_id: UUID,
    ) -> tuple[bool, UUID | None]:
        """Cancel product work and return the exact engine task to notify."""
        job = await self.get(job_id, knowledgebase_id, organization_id)
        changed, task_id = await AbsurdBoundWorkService(
            KnowledgeIngestionJobModel,
            self.session,
        ).cancel(
            work_id=job_id,
            organization_id=organization_id,
        )
        if changed:
            register_ingestion_lifecycle(job, KnowledgeWorkTransition.CANCELLED)
        return changed, task_id

    # ---- reads -------------------------------------------------------

    async def get(
        self,
        job_id: UUID,
        knowledgebase_id: UUID,
        organization_id: UUID,
    ) -> KnowledgeIngestionJobModel:
        result = await self.session.execute(
            select(KnowledgeIngestionJobModel).where(
                KnowledgeIngestionJobModel.id == job_id,
                KnowledgeIngestionJobModel.knowledgebase_id == knowledgebase_id,
                KnowledgeIngestionJobModel.organization_id == organization_id,
                KnowledgeIngestionJobModel.deleted.is_(False),
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise IngestionError(f"No ingestion job {job_id}.")
        return job

    async def list_for_knowledgebase(
        self,
        knowledgebase_id: UUID,
        organization_id: UUID,
        *,
        states: list[IngestionState] | None = None,
        limit: int = 50,
    ) -> list[KnowledgeIngestionJobModel]:
        query = select(KnowledgeIngestionJobModel).where(
            KnowledgeIngestionJobModel.knowledgebase_id == knowledgebase_id,
            KnowledgeIngestionJobModel.organization_id == organization_id,
            KnowledgeIngestionJobModel.deleted.is_(False),
        )
        if states:
            query = query.where(KnowledgeIngestionJobModel.state.in_(states))
        query = query.order_by(KnowledgeIngestionJobModel.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _find_active(
        self,
        organization_id: UUID,
        knowledgebase_id: UUID,
        document_id: UUID,
    ) -> KnowledgeIngestionJobModel | None:
        result = await self.session.execute(
            select(KnowledgeIngestionJobModel).where(
                KnowledgeIngestionJobModel.knowledgebase_id == knowledgebase_id,
                KnowledgeIngestionJobModel.organization_id == organization_id,
                KnowledgeIngestionJobModel.document_id == document_id,
                KnowledgeIngestionJobModel.state.in_(
                    [IngestionState.PENDING, IngestionState.RUNNING]
                ),
                # Soft-deleted rows are invisible to `claim`, so one left here
                # would block its document from ever being re-enqueued while
                # never running itself — a document that can be neither
                # ingested nor retried.
                KnowledgeIngestionJobModel.deleted.is_(False),
            )
        )
        return result.scalars().first()

    async def _require_target(
        self,
        knowledgebase_id: UUID,
        organization_id: UUID,
        *,
        scope: KnowledgeScope,
        scope_id: str,
    ) -> EmbeddingSpace | None:
        """Load the live KB and reject authority that does not belong in it."""
        record = (
            await self.session.execute(
                select(KnowledgebaseModel)
                .where(
                    KnowledgebaseModel.id == knowledgebase_id,
                    KnowledgebaseModel.organization_id == organization_id,
                    KnowledgebaseModel.deleted.is_(False),
                )
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        if record is None:
            raise IngestionError(f"No knowledgebase {knowledgebase_id}.")
        if (
            KnowledgeScope(record.scope) is not scope
            or str(record.scope_id) != str(scope_id)
        ):
            raise IngestionError(
                "Document scope does not match the target knowledgebase."
            )
        return embedding_space_from_record(record)


def _embedding_job_fields(space: EmbeddingSpace | None) -> dict[str, object]:
    if space is None:
        return {}
    return {
        "embedding_provider_config_id": space.provider_config_id,
        "embedding_provider_config_revision": space.provider_config_revision,
        "embedding_provider": space.provider,
        "embedding_endpoint": space.endpoint,
        "embedding_model": space.model,
        "embedding_dimensions": space.dimensions,
        "embedding_semantic_options": dict(space.semantic_options),
        "embedding_space_id": space.id,
    }


def document_from_job(
    job: KnowledgeIngestionJobModel, *, content: str | None = None
) -> KnowledgeDocument:
    """Rebuild the document a job describes.

    `content` is passed in for a storage-backed job, where the bytes were
    fetched at run time and were never on the row. Round-trips through the same
    type the enqueuer used, so the identity the worker computes is the identity
    the job was filed under — and when it is not, the worker notices, because
    chunks written under an id no job refers to are unreachable forever.
    """
    body = content if content is not None else job.content
    if body is None:
        raise IngestionError(
            f"Job {job.id} has neither inline content nor fetched content."
        )
    return KnowledgeDocument(
        content=body,
        scope=KnowledgeScope(job.scope),
        scope_id=job.scope_id,
        title=job.title,
        source_uri=job.source_uri,
        metadata=job.meta or {},
    )
