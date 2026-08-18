"""Application services for the `knowledgebase` domain."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import AbsurdBoundWorkService
from eylo.common.contracts.storage import StorageAuthority
from eylo.durable_runtime import DURABLE_MAX_ATTEMPTS
from eylo.events.schema.py_events.knowledgebase import KnowledgeWorkTransition
from eylo.modules.knowledgebase.events import register_corpus_lifecycle
from eylo.modules.knowledgebase.extraction import is_supported
from eylo.modules.knowledgebase.jobs import (
    MAX_CORPUS_OBJECTS,
    MAX_STORAGE_OBJECT_BYTES,
    CorpusImportState,
    KnowledgeCorpusImportModel,
)
from eylo.modules.knowledgebase.models import KnowledgebaseModel

logger = logging.getLogger(__name__)


class CorpusImportError(Exception):
    """An import could not be started or advanced."""


# Screening asks the extraction registry rather than keeping its own list.
# Two lists would drift, and the failure when they did would be an object
# screened in that no extractor can read — or worse, one screened out that
# could have been.
is_importable = is_supported


class CorpusImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        knowledgebase_id: UUID,
        prefix: str,
        storage_authority: StorageAuthority,
    ) -> KnowledgeCorpusImportModel:
        """Record the intent to sweep a prefix. Reads nothing yet."""
        if str(storage_authority.organization_id) != str(organization_id):
            raise CorpusImportError(
                "Storage authority must belong to the corpus organization."
            )
        live = await self.session.scalar(
            select(KnowledgebaseModel.id)
            .where(
                KnowledgebaseModel.id == knowledgebase_id,
                KnowledgebaseModel.organization_id == organization_id,
                KnowledgebaseModel.deleted.is_(False),
            )
            .with_for_update(read=True)
        )
        if live is None:
            raise CorpusImportError("Knowledgebase not found.")
        import_key = _import_key(prefix, storage_authority)
        existing = await self._find_active(
            organization_id,
            knowledgebase_id,
            import_key,
        )
        if existing is not None:
            # Two sweeps of one prefix would file the same jobs and race each
            # other doing it. The second is answered with the first rather than
            # refused, because asking twice is a retry, not an error.
            logger.info(
                "A corpus import of '%s' is already %s; returning %s.",
                prefix, existing.state.value, existing.id,
            )
            return existing

        record = KnowledgeCorpusImportModel(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            prefix=prefix,
            import_key=import_key,
            storage_provider_config_id=storage_authority.provider_config_id,
            storage_provider_config_revision=(
                storage_authority.provider_config_revision
            ),
            storage_provider=storage_authority.provider,
            storage_authority=dict(storage_authority.location),
            state=CorpusImportState.PENDING,
            max_attempts=DURABLE_MAX_ATTEMPTS,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            winner = await self._find_active(
                organization_id,
                knowledgebase_id,
                import_key,
            )
            if winner is None:
                raise
            return winner
        register_corpus_lifecycle(record, KnowledgeWorkTransition.QUEUED)
        return record

    async def cancel(
        self,
        import_id: UUID,
        knowledgebase_id: UUID,
        organization_id: UUID,
    ) -> tuple[bool, UUID | None]:
        """Stop a sweep. Jobs it already filed keep running.

        Cancelling the sweep does not cancel the documents it found — those are
        real work already accepted, and an operator who wants them gone cancels
        the jobs.
        """
        record = await self.get(import_id, knowledgebase_id, organization_id)
        changed, task_id = await AbsurdBoundWorkService(
            KnowledgeCorpusImportModel,
            self.session,
        ).cancel(
            work_id=import_id,
            organization_id=organization_id,
        )
        if changed:
            register_corpus_lifecycle(record, KnowledgeWorkTransition.CANCELLED)
        return changed, task_id

    async def get(
        self,
        import_id: UUID,
        knowledgebase_id: UUID,
        organization_id: UUID,
    ) -> KnowledgeCorpusImportModel:
        result = await self.session.execute(
            select(KnowledgeCorpusImportModel).where(
                KnowledgeCorpusImportModel.id == import_id,
                KnowledgeCorpusImportModel.knowledgebase_id == knowledgebase_id,
                KnowledgeCorpusImportModel.organization_id == organization_id,
                KnowledgeCorpusImportModel.deleted.is_(False),
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise CorpusImportError(f"No corpus import {import_id}.")
        return record

    async def list_for_knowledgebase(
        self, knowledgebase_id: UUID, organization_id: UUID, *, limit: int = 50
    ) -> list[KnowledgeCorpusImportModel]:
        result = await self.session.execute(
            select(KnowledgeCorpusImportModel)
            .where(
                KnowledgeCorpusImportModel.knowledgebase_id == knowledgebase_id,
                KnowledgeCorpusImportModel.organization_id == organization_id,
                KnowledgeCorpusImportModel.deleted.is_(False),
            )
            .order_by(KnowledgeCorpusImportModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _find_active(
        self,
        organization_id: UUID,
        knowledgebase_id: UUID,
        import_key: str,
    ) -> KnowledgeCorpusImportModel | None:
        result = await self.session.execute(
            select(KnowledgeCorpusImportModel).where(
                KnowledgeCorpusImportModel.knowledgebase_id == knowledgebase_id,
                KnowledgeCorpusImportModel.organization_id == organization_id,
                KnowledgeCorpusImportModel.import_key == import_key,
                KnowledgeCorpusImportModel.state.in_(
                    [CorpusImportState.PENDING, CorpusImportState.RUNNING]
                ),
                # Matches both `claim` and the partial unique index. All three
                # have to agree on what "active" means, or a
                # soft-deleted row blocks a prefix it will never sweep.
                KnowledgeCorpusImportModel.deleted.is_(False),
            )
        )
        return result.scalars().first()


def _import_key(prefix: str, authority: StorageAuthority) -> str:
    identity = (
        f"{prefix}\0{authority.provider_config_id}\0"
        f"{authority.provider_config_revision}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def screen(objects) -> tuple[list, list[dict]]:
    """Split a listing into what will be queued and what will not, with reasons.

    Screening happens before any object is fetched, which is the only point at
    which refusing an oversized file costs nothing. Both halves are returned
    because an import that reports only what it took is indistinguishable from
    one that took everything.
    """
    keep, skipped = [], []
    for entry in objects:
        if not is_importable(entry.key):
            skipped.append({"key": entry.key, "reason": "unsupported file type"})
        elif entry.size > MAX_STORAGE_OBJECT_BYTES:
            skipped.append(
                {
                    "key": entry.key,
                    "reason": f"{entry.size} bytes exceeds the "
                    f"{MAX_STORAGE_OBJECT_BYTES} byte limit",
                }
            )
        elif entry.size == 0:
            skipped.append({"key": entry.key, "reason": "empty object"})
        else:
            keep.append(entry)
    if len(objects) >= MAX_CORPUS_OBJECTS:
        # Said out loud. A silent ceiling reads as "your corpus is imported"
        # when it means "the first five thousand of it are".
        logger.warning(
            "Corpus listing hit the %d object ceiling; there may be more under "
            "this prefix that were never enumerated.",
            MAX_CORPUS_OBJECTS,
        )
    return keep, skipped
