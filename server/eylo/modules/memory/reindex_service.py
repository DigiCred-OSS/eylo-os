"""Memory active-space authority and atomic staged re-embedding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import AbsurdBoundWorkService, DurableState
from eylo.common.contracts.embedding import (
    EmbeddingError,
    EmbeddingSpace,
    embedding_space_from_record,
    source_embedding_space_from_record,
    target_embedding_space_from_record,
)
from eylo.common.contracts.memory import MemoryError
from eylo.durable_runtime import DURABLE_MAX_ATTEMPTS
from eylo.events.schema.py_events.memory import MemoryReindexTransition
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.memory.events import register_reindex_lifecycle
from eylo.modules.memory.models import (
    MemoryFormationJobModel,
    MemoryIndexModel,
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationJobModel,
    MemoryReindexJobModel,
    MemoryReindexVectorModel,
)
from eylo.modules.memory.reindex import MemoryReindexState
from eylo.modules.provider_configs.errors import NotConfiguredError

MEMORY_REINDEX_BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class ReindexFact:
    id: UUID
    content: str
    state_revision: int


def _safe_failure_summary(error: Exception) -> str:
    """Return bounded operator detail without persisting provider exceptions."""
    if isinstance(error, (InvalidEmbeddingConfig, NotConfiguredError)):
        return "Memory embedding configuration is unavailable."
    if isinstance(error, EmbeddingError):
        return "Memory embedding provider could not complete the reindex."
    if isinstance(error, MemoryError):
        return "Memory reindex authority is invalid."
    return "Memory reindex failed."


def _safe_failure_code(error: Exception) -> str:
    if isinstance(error, (InvalidEmbeddingConfig, NotConfiguredError)):
        return "memory_embedding_not_configured"
    if isinstance(error, EmbeddingError):
        return "memory_embedding_failed"
    if isinstance(error, MemoryError):
        return "memory_reindex_invalid"
    return "memory_reindex_failed"


class MemoryReindexService:
    """Own active authority, staged vectors, and one atomic Memory cutover."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_verified_space(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
        verified_space: EmbeddingSpace,
    ) -> MemoryIndexModel:
        if verified_space.organization_id != organization_id:
            raise MemoryError("Memory embedding space belongs to another organization.")
        index = await self._index(
            organization_id,
            memory_provider_config_id,
            for_update=True,
            required=False,
        )
        if index is None:
            index = MemoryIndexModel(
                organization_id=organization_id,
                memory_provider_config_id=memory_provider_config_id,
                **_space_fields(verified_space, prefix="embedding"),
            )
            self.session.add(index)
            await self.session.flush()
            return index

        active = embedding_space_from_record(index)
        if active is None:
            raise MemoryError("Memory index has no active embedding authority.")
        staged = target_embedding_space_from_record(index)
        if index.reindex_state is not MemoryReindexState.ACTIVE:
            was_failed = index.reindex_state is MemoryReindexState.FAILED
            if staged is None or not staged.is_compatible_with(verified_space):
                raise MemoryError(
                    "Memory has a pending reindex; finish it before changing space."
                )
            for field, value in _space_fields(
                verified_space,
                prefix="target_embedding",
            ).items():
                setattr(index, field, value)
            if index.reindex_state is MemoryReindexState.FAILED:
                index.reindex_state = MemoryReindexState.REQUIRED
                index.reindex_last_error = None
            await self.session.flush()
            if was_failed:
                register_reindex_lifecycle(
                    index,
                    MemoryReindexTransition.REINDEX_REQUIRED,
                )
            return index

        if active.is_compatible_with(verified_space):
            for field, value in _space_fields(
                verified_space,
                prefix="embedding",
            ).items():
                setattr(index, field, value)
            await self.session.flush()
            return index

        for field, value in _space_fields(
            verified_space,
            prefix="target_embedding",
        ).items():
            setattr(index, field, value)
        index.reindex_state = MemoryReindexState.REQUIRED
        index.reindex_last_error = None
        await self.session.flush()
        register_reindex_lifecycle(
            index,
            MemoryReindexTransition.REINDEX_REQUIRED,
        )
        return index

    async def active_space(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
    ) -> EmbeddingSpace:
        index = await self._index(
            organization_id,
            memory_provider_config_id,
            required=True,
        )
        space = embedding_space_from_record(index)
        if space is None:
            raise MemoryError("Memory index has no active embedding authority.")
        return space

    async def index(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
    ) -> MemoryIndexModel | None:
        return await self._index(
            organization_id,
            memory_provider_config_id,
            required=False,
        )

    async def latest_job(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
    ) -> MemoryReindexJobModel | None:
        return await self.session.scalar(
            select(MemoryReindexJobModel)
            .where(
                MemoryReindexJobModel.organization_id == organization_id,
                MemoryReindexJobModel.memory_provider_config_id
                == memory_provider_config_id,
                MemoryReindexJobModel.deleted.is_(False),
            )
            .order_by(
                MemoryReindexJobModel.created_at.desc(),
                MemoryReindexJobModel.id.desc(),
            )
            .limit(1)
        )

    async def lock_active_space(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
    ) -> EmbeddingSpace:
        """Fence formation filing against a concurrent atomic cutover."""
        index = await self._index(
            organization_id,
            memory_provider_config_id,
            for_share=True,
            required=True,
        )
        space = embedding_space_from_record(index)
        if space is None:
            raise MemoryError("Memory index has no active embedding authority.")
        return space

    async def request(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
        max_attempts: int = DURABLE_MAX_ATTEMPTS,
    ) -> MemoryReindexJobModel:
        index = await self._index(
            organization_id,
            memory_provider_config_id,
            for_update=True,
            required=True,
        )
        source = embedding_space_from_record(index)
        target = target_embedding_space_from_record(index)
        if source is None or target is None:
            raise MemoryError("Memory config has no pending embedding-space change.")

        active = await self.session.scalar(
            select(MemoryReindexJobModel).where(
                MemoryReindexJobModel.organization_id == organization_id,
                MemoryReindexJobModel.memory_provider_config_id
                == memory_provider_config_id,
                MemoryReindexJobModel.state.in_(
                    (DurableState.PENDING, DurableState.RUNNING)
                ),
                MemoryReindexJobModel.deleted.is_(False),
            )
        )
        if active is not None:
            active_target = target_embedding_space_from_record(active)
            if active_target is not None and active_target.is_compatible_with(target):
                return active
            raise MemoryError("Memory config already has an active reindex.")

        job = MemoryReindexJobModel(
            organization_id=organization_id,
            memory_provider_config_id=memory_provider_config_id,
            max_attempts=max_attempts,
            **_space_fields(source, prefix="source_embedding"),
            **_space_fields(target, prefix="target_embedding"),
        )
        self.session.add(job)
        index.reindex_state = MemoryReindexState.REQUIRED
        index.reindex_last_error = None
        await self.session.flush()
        register_reindex_lifecycle(
            index,
            MemoryReindexTransition.QUEUED,
            job=job,
        )
        return job

    async def begin_attempt(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReindexJobModel:
        job = await AbsurdBoundWorkService(
            MemoryReindexJobModel,
            self.session,
        ).begin_attempt(work_id=job_id, organization_id=organization_id)
        if job.state not in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            index = await self._index(
                organization_id,
                job.memory_provider_config_id,
                for_update=True,
                required=True,
            )
            register_reindex_lifecycle(
                index,
                MemoryReindexTransition.ATTEMPT_STARTED,
                job=job,
            )
        return job

    async def prepare_attempt(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReindexJobModel:
        job = await AbsurdBoundWorkService(
            MemoryReindexJobModel,
            self.session,
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
            return job
        if job.state is not DurableState.RUNNING:
            raise MemoryError("Memory reindex attempt is not running.")
        index = await self._index(
            organization_id,
            job.memory_provider_config_id,
            for_update=True,
            required=True,
        )
        source = source_embedding_space_from_record(job)
        target = target_embedding_space_from_record(job)
        active = embedding_space_from_record(index)
        staged = target_embedding_space_from_record(index)
        if (
            source is None
            or target is None
            or active is None
            or staged is None
            or source.id != active.id
            or target.id != staged.id
        ):
            raise MemoryError("Memory reindex authority changed.")
        index.reindex_state = MemoryReindexState.REINDEXING
        index.reindex_last_error = None
        await self.session.flush()
        return job

    async def next_batch(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        limit: int = MEMORY_REINDEX_BATCH_SIZE,
    ) -> list[ReindexFact]:
        job = await self._running_job(organization_id, job_id)
        rows = await self.session.execute(
            sql(
                """
                SELECT fact.id, fact.content, fact.state_revision
                FROM memory_memories AS fact
                WHERE fact.organization_id = :organization_id
                  AND fact.memory_provider_config_id = :memory_config_id
                  AND fact.embedding_space_id = :source_space_id
                  AND fact.deleted IS FALSE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM memory_reindex_vectors AS staged
                      WHERE staged.organization_id = fact.organization_id
                        AND staged.reindex_job_id = :job_id
                        AND staged.memory_id = fact.id
                        AND staged.source_state_revision = fact.state_revision
                        AND staged.deleted IS FALSE
                  )
                ORDER BY fact.id
                LIMIT :limit
                """
            ),
            {
                "organization_id": organization_id,
                "memory_config_id": job.memory_provider_config_id,
                "source_space_id": job.source_embedding_space_id,
                "job_id": job_id,
                "limit": limit,
            },
        )
        return [
            ReindexFact(
                id=UUID(str(row.id)),
                content=row.content,
                state_revision=row.state_revision,
            )
            for row in rows
        ]

    async def store_vectors(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        facts: Sequence[ReindexFact],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        if len(facts) != len(vectors):
            raise MemoryError("Memory reindex embedding returned a partial batch.")
        job = await self._running_job(organization_id, job_id)
        if any(len(vector) != job.target_embedding_dimensions for vector in vectors):
            raise MemoryError("Memory reindex embedding dimensions are invalid.")
        stored = 0
        for fact, vector in zip(facts, vectors, strict=True):
            result = await self.session.execute(
                sql(
                    """
                    INSERT INTO memory_reindex_vectors
                        (id, organization_id, reindex_job_id, memory_id,
                         source_state_revision, embedding, deleted,
                         created_at, updated_at)
                    SELECT gen_random_uuid(), fact.organization_id, :job_id,
                           fact.id, fact.state_revision,
                           CAST(:embedding AS vector), false, now(), now()
                    FROM memory_memories AS fact
                    WHERE fact.id = :memory_id
                      AND fact.organization_id = :organization_id
                      AND fact.memory_provider_config_id = :memory_config_id
                      AND fact.embedding_space_id = :source_space_id
                      AND fact.state_revision = :source_state_revision
                      AND fact.deleted IS FALSE
                    ON CONFLICT (reindex_job_id, memory_id)
                    DO UPDATE SET
                        source_state_revision = EXCLUDED.source_state_revision,
                        embedding = EXCLUDED.embedding,
                        deleted = false,
                        updated_at = now()
                    """
                ),
                {
                    "organization_id": organization_id,
                    "job_id": job_id,
                    "memory_id": fact.id,
                    "memory_config_id": job.memory_provider_config_id,
                    "source_space_id": job.source_embedding_space_id,
                    "source_state_revision": fact.state_revision,
                    "embedding": _vector(vector),
                },
            )
            stored += int(result.rowcount or 0)
        await self.session.flush()
        return stored

    async def finalize_if_caught_up(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> bool:
        work = AbsurdBoundWorkService(MemoryReindexJobModel, self.session)
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        if job.state is DurableState.SUCCEEDED:
            return True
        if job.state is not DurableState.RUNNING:
            raise MemoryError("Memory reindex cutover is not running.")
        index = await self._index(
            organization_id,
            job.memory_provider_config_id,
            for_update=True,
            required=True,
        )
        source = source_embedding_space_from_record(job)
        target = target_embedding_space_from_record(job)
        active = embedding_space_from_record(index)
        staged = target_embedding_space_from_record(index)
        if (
            source is None
            or target is None
            or active is None
            or staged is None
            or source.id != active.id
            or target.id != staged.id
        ):
            raise MemoryError("Memory reindex fence changed.")

        missing = await self.session.scalar(
            sql(
                """
                SELECT count(*)
                FROM memory_memories AS fact
                WHERE fact.organization_id = :organization_id
                  AND fact.memory_provider_config_id = :memory_config_id
                  AND fact.embedding_space_id = :source_space_id
                  AND fact.deleted IS FALSE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM memory_reindex_vectors AS staged
                      WHERE staged.organization_id = fact.organization_id
                        AND staged.reindex_job_id = :job_id
                        AND staged.memory_id = fact.id
                        AND staged.source_state_revision = fact.state_revision
                        AND staged.deleted IS FALSE
                  )
                """
            ),
            {
                "organization_id": organization_id,
                "memory_config_id": job.memory_provider_config_id,
                "source_space_id": job.source_embedding_space_id,
                "job_id": job_id,
            },
        )
        active_formations = await self.session.scalar(
            select(func.count())
            .select_from(MemoryFormationJobModel)
            .where(
                MemoryFormationJobModel.organization_id == organization_id,
                MemoryFormationJobModel.memory_provider_config_id
                == job.memory_provider_config_id,
                MemoryFormationJobModel.embedding_space_id
                == job.source_embedding_space_id,
                MemoryFormationJobModel.state.in_(
                    (DurableState.PENDING, DurableState.RUNNING)
                ),
                MemoryFormationJobModel.deleted.is_(False),
            )
        )
        active_reconciliations = await self.session.scalar(
            select(func.count())
            .select_from(MemoryReconciliationJobModel)
            .where(
                MemoryReconciliationJobModel.organization_id == organization_id,
                MemoryReconciliationJobModel.memory_provider_config_id
                == job.memory_provider_config_id,
                MemoryReconciliationJobModel.embedding_space_id
                == job.source_embedding_space_id,
                MemoryReconciliationJobModel.state.in_(
                    (DurableState.PENDING, DurableState.RUNNING)
                ),
                MemoryReconciliationJobModel.deleted.is_(False),
            )
        )
        if missing or active_formations or active_reconciliations:
            return False

        source_count = int(
            await self.session.scalar(
                select(func.count())
                .select_from(MemoryModel)
                .where(
                    MemoryModel.organization_id == organization_id,
                    MemoryModel.memory_provider_config_id
                    == job.memory_provider_config_id,
                    MemoryModel.embedding_space_id == job.source_embedding_space_id,
                    MemoryModel.deleted.is_(False),
                )
            )
            or 0
        )
        staged_count = int(
            await self.session.scalar(
                sql(
                    """
                    SELECT count(*)
                    FROM memory_reindex_vectors AS staged
                    JOIN memory_memories AS fact
                      ON fact.id = staged.memory_id
                     AND fact.organization_id = staged.organization_id
                     AND fact.state_revision = staged.source_state_revision
                    WHERE staged.organization_id = :organization_id
                      AND staged.reindex_job_id = :job_id
                      AND staged.deleted IS FALSE
                      AND fact.memory_provider_config_id = :memory_config_id
                      AND fact.embedding_space_id = :source_space_id
                      AND fact.deleted IS FALSE
                    """
                )
                .bindparams(
                    organization_id=organization_id,
                    job_id=job_id,
                    memory_config_id=job.memory_provider_config_id,
                    source_space_id=job.source_embedding_space_id,
                )
            )
            or 0
        )
        if source_count != staged_count:
            raise MemoryError("Memory reindex target is not a complete source copy.")

        cutover = await self.session.execute(
            sql(
                """
                UPDATE memory_memories AS fact
                SET embedding = staged.embedding,
                    embedding_provider_config_id = :target_config_id,
                    embedding_provider_config_revision = :target_revision,
                    embedding_provider = :target_provider,
                    embedding_endpoint = :target_endpoint,
                    embedding_model = :target_model,
                    embedding_dimensions = :target_dimensions,
                    embedding_semantic_options = CAST(:target_options AS jsonb),
                    embedding_space_id = :target_space_id
                FROM memory_reindex_vectors AS staged
                WHERE staged.organization_id = :organization_id
                  AND staged.reindex_job_id = :job_id
                  AND staged.memory_id = fact.id
                  AND staged.source_state_revision = fact.state_revision
                  AND staged.deleted IS FALSE
                  AND fact.organization_id = :organization_id
                  AND fact.memory_provider_config_id = :memory_config_id
                  AND fact.embedding_space_id = :source_space_id
                  AND fact.deleted IS FALSE
                """
            ),
            {
                "organization_id": organization_id,
                "job_id": job_id,
                "memory_config_id": job.memory_provider_config_id,
                "source_space_id": source.id,
                "target_config_id": target.provider_config_id,
                "target_revision": target.provider_config_revision,
                "target_provider": target.provider,
                "target_endpoint": target.endpoint,
                "target_model": target.model,
                "target_dimensions": target.dimensions,
                "target_options": _json(target.semantic_options),
                "target_space_id": target.id,
            },
        )
        if int(cutover.rowcount or 0) != source_count:
            raise MemoryError("Memory reindex cutover did not update every fact.")

        # A cursor is mutable filing authority, unlike its immutable change
        # evidence and already-filed jobs. Active source-space jobs fence this
        # cutover above; move the remaining unfiled cursors with the facts so
        # their backlog can be reconciled against the new active space.
        await self.session.execute(
            update(MemoryReconciliationCursorModel)
            .where(
                MemoryReconciliationCursorModel.organization_id == organization_id,
                MemoryReconciliationCursorModel.memory_provider_config_id
                == job.memory_provider_config_id,
                MemoryReconciliationCursorModel.embedding_space_id == source.id,
                MemoryReconciliationCursorModel.active_job_id.is_(None),
                MemoryReconciliationCursorModel.deleted.is_(False),
            )
            .values(
                **_space_fields(target, prefix="embedding"),
                updated_at=func.now(),
            )
        )
        self._activate_target(index)
        await self.session.execute(
            delete(MemoryReindexVectorModel).where(
                MemoryReindexVectorModel.organization_id == organization_id,
                MemoryReindexVectorModel.reindex_job_id == job_id,
            )
        )
        completed = await work.succeed(
            work_id=job_id,
            organization_id=organization_id,
            values={
                "source_fact_count": source_count,
                "indexed_fact_count": staged_count,
            },
        )
        register_reindex_lifecycle(
            index,
            MemoryReindexTransition.SUCCEEDED,
            job=completed,
        )
        return True

    async def record_failure(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        error: Exception,
        permanent: bool,
    ) -> DurableState:
        work = AbsurdBoundWorkService(MemoryReindexJobModel, self.session)
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = job.state is DurableState.RUNNING
        state = await work.fail(
            work_id=job_id,
            organization_id=organization_id,
            error=_safe_failure_summary(error),
            permanent=permanent,
        )
        if not was_running:
            return state
        index = await self._index(
            organization_id,
            job.memory_provider_config_id,
            for_update=True,
            required=True,
        )
        if state is DurableState.FAILED:
            if index.target_embedding_space_id == job.target_embedding_space_id:
                index.reindex_state = MemoryReindexState.FAILED
                index.reindex_last_error = job.last_error
            await self.session.execute(
                delete(MemoryReindexVectorModel).where(
                    MemoryReindexVectorModel.organization_id == organization_id,
                    MemoryReindexVectorModel.reindex_job_id == job_id,
                )
            )
            await self.session.flush()
        register_reindex_lifecycle(
            index,
            (
                MemoryReindexTransition.RETRY_SCHEDULED
                if state is DurableState.PENDING
                else MemoryReindexTransition.FAILED
            ),
            job=job,
            failure_code=_safe_failure_code(error),
        )
        return state

    async def discard_pending(
        self,
        *,
        organization_id: UUID,
        memory_provider_config_id: UUID,
    ) -> MemoryIndexModel:
        index = await self._index(
            organization_id,
            memory_provider_config_id,
            for_update=True,
            required=True,
        )
        if index.reindex_state is MemoryReindexState.ACTIVE:
            return index
        active_job = await self.session.scalar(
            select(MemoryReindexJobModel.id).where(
                MemoryReindexJobModel.organization_id == organization_id,
                MemoryReindexJobModel.memory_provider_config_id
                == memory_provider_config_id,
                MemoryReindexJobModel.state.in_(
                    (DurableState.PENDING, DurableState.RUNNING)
                ),
                MemoryReindexJobModel.deleted.is_(False),
            )
        )
        if active_job is not None:
            raise MemoryError("Cancel the active Memory reindex before discarding it.")
        source_space_id = index.embedding_space_id
        target_space_id = index.target_embedding_space_id
        latest_job = await self.latest_job(
            organization_id=organization_id,
            memory_provider_config_id=memory_provider_config_id,
        )
        self._clear_target(index)
        await self.session.flush()
        if target_space_id is not None:
            register_reindex_lifecycle(
                index,
                MemoryReindexTransition.TARGET_DISCARDED,
                job=(
                    latest_job
                    if latest_job is not None
                    and latest_job.target_embedding_space_id == target_space_id
                    else None
                ),
                source_embedding_space_id=source_space_id,
                target_embedding_space_id=target_space_id,
            )
        return index

    async def cancel(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> None:
        work = AbsurdBoundWorkService(MemoryReindexJobModel, self.session)
        changed, _task_id = await work.cancel(
            work_id=job_id,
            organization_id=organization_id,
        )
        if not changed:
            return
        job = await work.get(work_id=job_id, organization_id=organization_id)
        index = await self._index(
            organization_id,
            job.memory_provider_config_id,
            for_update=True,
            required=True,
        )
        active = embedding_space_from_record(index)
        if (
            active is not None
            and active.id == job.source_embedding_space_id
            and index.target_embedding_space_id == job.target_embedding_space_id
        ):
            index.reindex_state = MemoryReindexState.REQUIRED
            index.reindex_last_error = None
        await self.session.execute(
            delete(MemoryReindexVectorModel).where(
                MemoryReindexVectorModel.organization_id == organization_id,
                MemoryReindexVectorModel.reindex_job_id == job_id,
            )
        )
        await self.session.flush()
        register_reindex_lifecycle(
            index,
            MemoryReindexTransition.CANCELLED,
            job=job,
        )

    async def get_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReindexJobModel:
        return await self._job(organization_id, job_id)

    async def _index(
        self,
        organization_id: UUID,
        memory_provider_config_id: UUID,
        *,
        for_update: bool = False,
        for_share: bool = False,
        required: bool,
    ) -> MemoryIndexModel | None:
        if for_update and for_share:
            raise ValueError("Memory index lock mode is ambiguous.")
        query = select(MemoryIndexModel).where(
            MemoryIndexModel.organization_id == organization_id,
            MemoryIndexModel.memory_provider_config_id
            == memory_provider_config_id,
            MemoryIndexModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        elif for_share:
            query = query.with_for_update(read=True)
        index = await self.session.scalar(query)
        if index is None and required:
            raise MemoryError("Memory config has no verified embedding index.")
        return index

    async def _job(
        self,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReindexJobModel:
        return await AbsurdBoundWorkService(
            MemoryReindexJobModel,
            self.session,
        ).get(work_id=job_id, organization_id=organization_id)

    async def _running_job(
        self,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReindexJobModel:
        job = await self._job(organization_id, job_id)
        if job.state is not DurableState.RUNNING:
            raise MemoryError("Memory reindex batch is not running.")
        return job

    @staticmethod
    def _activate_target(index: MemoryIndexModel) -> None:
        target = target_embedding_space_from_record(index)
        if target is None:
            raise MemoryError("Memory reindex target is missing.")
        for field, value in _space_fields(target, prefix="embedding").items():
            setattr(index, field, value)
        MemoryReindexService._clear_target(index)

    @staticmethod
    def _clear_target(index: MemoryIndexModel) -> None:
        for field in (
            "target_embedding_provider_config_id",
            "target_embedding_provider_config_revision",
            "target_embedding_provider",
            "target_embedding_endpoint",
            "target_embedding_model",
            "target_embedding_dimensions",
            "target_embedding_semantic_options",
            "target_embedding_space_id",
        ):
            setattr(index, field, None)
        index.reindex_state = MemoryReindexState.ACTIVE
        index.reindex_last_error = None


def _space_fields(space: EmbeddingSpace, *, prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_provider_config_id": space.provider_config_id,
        f"{prefix}_provider_config_revision": space.provider_config_revision,
        f"{prefix}_provider": space.provider,
        f"{prefix}_endpoint": space.endpoint,
        f"{prefix}_model": space.model,
        f"{prefix}_dimensions": space.dimensions,
        f"{prefix}_semantic_options": dict(space.semantic_options),
        f"{prefix}_space_id": space.id,
    }


def _vector(values: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _json(value: object) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)
