"""Memory in Postgres, retrieved by embedding similarity.

Raw SQL against `memory_memories` and `memory_changes`, because a socket may
not import from `modules/` and that is where the tables are declared — the same
arrangement the knowledgebase vendors use.

The embedder and the completion function are both injected. Resolving either
needs a provider config, which lives in `modules/`, so this stays ignorant of
where credentials come from.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4, uuid5

from pydantic import ValidationError
from sqlalchemy import text as sql
from sqlalchemy.exc import SQLAlchemyError

from eylo.common.contracts.embedding import EmbeddingSpace
from eylo.sockets.memory.base import MemoryVendorAdapter
from eylo.sockets.memory.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    RELATED_LIMIT,
    build_prompt,
    parse_operations,
)
from eylo.sockets.memory.reconciliation import RECONCILIATION_PROMPT_REVISION
from eylo.sockets.memory.schemas import (
    MEMORY_MAX_OPERATIONS,
    MEMORY_MAX_SEARCH_RESULTS,
    Memory,
    MemoryActor,
    MemoryCapabilities,
    MemoryChange,
    MemoryError,
    MemoryEvent,
    MemoryExtractionAuthority,
    MemoryInputMessage,
    MemoryLevel,
    MemoryOperation,
    MemoryOrigin,
    MemoryOutcomeCounts,
    MemoryProvenance,
    MemoryResult,
    MemoryScope,
    MemoryUpdateResult,
    require_memory_fact,
    require_memory_query,
)

logger = logging.getLogger(__name__)

PROVIDER = "pgvector"


def _vector(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _digest(content: str) -> str:
    return hashlib.sha256(content.strip().lower().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _FactSnapshot:
    id: UUID
    content: str
    state_revision: int
    expired: bool


class PgVectorMemoryAdapter(MemoryVendorAdapter):
    """Our own memory implementation."""

    def __init__(
        self,
        session_factory,
        document_embedder,
        query_embedder,
        completer,
        embedding_space: EmbeddingSpace,
        *,
        memory_provider_config_id: UUID,
        memory_provider_config_revision: int,
        extraction_authority: MemoryExtractionAuthority,
        before_formation_commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Inject intent-specific embedders, extraction, and vector authority.

        Both injected rather than constructed: they resolve through the LLM
        capability, and a socket may not reach `modules/` to do that.
        """
        self._session_factory = session_factory
        self._document_embedder = document_embedder
        self._query_embedder = query_embedder
        self._completer = completer
        self._embedding_space = embedding_space
        self._memory_provider_config_id = memory_provider_config_id
        self._memory_provider_config_revision = memory_provider_config_revision
        self._extraction_authority = extraction_authority
        self._before_formation_commit = before_formation_commit

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> MemoryCapabilities:
        return MemoryCapabilities(
            semantic_search=True,
            keyword_search=False,
            infers_operations=True,
            history=True,
        )

    async def verify(self) -> None:
        """Exercise extraction, embeddings, pgvector, and the live table atomically."""
        content = f"memory verification {uuid4()}"
        document_vectors = await self._document_embedder([content])
        query_vector = await self._query_embedder(content)
        if len(document_vectors) != 1:
            raise MemoryError("Memory verification embedding count is invalid.")
        document_vector = document_vectors[0]
        dimensions = self._embedding_space.dimensions
        if len(document_vector) != dimensions or len(query_vector) != dimensions:
            raise MemoryError("Memory verification embedding dimensions are invalid.")
        await self._completer(
            system="Reply with the single word ready.",
            user="Memory verification contains no tenant data.",
        )

        async with self._session_factory() as session:
            distance = await session.scalar(
                sql("SELECT CAST(:document AS vector) <=> CAST(:query AS vector)"),
                {
                    "document": _vector(document_vector),
                    "query": _vector(query_vector),
                },
            )
            table_count = await session.scalar(
                sql(
                    "SELECT count(*) FROM memory_memories "
                    "WHERE organization_id = :organization_id "
                    "AND memory_provider_config_id = :memory_provider_config_id "
                    "AND embedding_space_id = :embedding_space_id"
                ),
                {
                    "organization_id": self._embedding_space.organization_id,
                    "embedding_space_id": self._embedding_space.id,
                    **self._memory_config_params(),
                },
            )
            if (
                distance is None
                or not math.isfinite(float(distance))
                or table_count is None
            ):
                raise MemoryError("Memory verification similarity is invalid.")

    # ---- the decision and atomic application flow -------------------

    async def add(
        self,
        messages: list[MemoryInputMessage],
        *,
        scope: MemoryScope,
        source_conversation_id: UUID,
        origin: MemoryOrigin,
        actor: MemoryActor | None,
        metadata: dict[str, Any] | None = None,
        formation_job_id: UUID | None = None,
    ) -> list[MemoryOperation]:
        """Validate one complete plan, then commit every outcome or none."""
        if (
            origin is MemoryOrigin.AUTOMATIC_FORMATION
            and self._require_conversation_scope(scope) != source_conversation_id
        ):
            raise MemoryError("Automatic memory formation changed its owner.")
        if formation_job_id is not None:
            return await self._add_formation(
                messages,
                scope=scope,
                source_conversation_id=source_conversation_id,
                origin=origin,
                actor=actor,
                metadata=metadata,
                formation_job_id=formation_job_id,
            )
        operations = await self._plan(messages, scope=scope)
        vectors = await self._operation_vectors(operations)
        try:
            async with self._session_factory() as session:
                applied = await self._apply_plan(
                    session,
                    operations=operations,
                    vectors=vectors,
                    scope=scope,
                    source_conversation_id=source_conversation_id,
                    origin=origin,
                    actor=actor,
                    metadata=metadata,
                    formation_job_id=None,
                )
                await session.commit()
                return applied
        except MemoryError:
            raise
        except SQLAlchemyError as error:
            logger.info("Memory plan rolled back: %s", type(error).__name__)
            raise MemoryError(
                "Memory plan conflicted with current facts.",
                vendor=PROVIDER,
                retryable=True,
            ) from None

    async def _add_formation(
        self,
        messages: list[MemoryInputMessage],
        *,
        scope: MemoryScope,
        source_conversation_id: UUID,
        origin: MemoryOrigin,
        actor: MemoryActor | None,
        metadata: dict[str, Any] | None,
        formation_job_id: UUID,
    ) -> list[MemoryOperation]:
        """Persist one immutable plan and commit its full outcome atomically."""
        completed = await self._completed_formation_result(
            formation_job_id,
            scope.organization_id,
        )
        if completed is not None:
            await self._guard_formation_commit()
            return completed
        operations = await self._formation_plan(
            messages,
            scope=scope,
            formation_job_id=formation_job_id,
        )
        vectors = await self._operation_vectors(operations)
        guard_error: Exception | None = None
        try:
            async with self._session_factory() as session:
                job_state = await session.scalar(
                    sql(
                        """
                        SELECT state::text
                        FROM memory_formation_jobs
                        WHERE id = :formation_job_id
                          AND organization_id = :organization_id
                          AND conversation_id = :conversation_id
                          AND deleted IS FALSE
                        FOR UPDATE
                        """
                    ),
                    {
                        "formation_job_id": formation_job_id,
                        "organization_id": scope.organization_id,
                        "conversation_id": self._require_conversation_scope(scope),
                    },
                )
                if job_state != "running":
                    raise MemoryError(
                        "Memory formation is no longer running.",
                        vendor=PROVIDER,
                    )
                effect = (
                    await session.execute(
                        sql(
                            """
                            SELECT operations, outcomes, finished_at
                            FROM memory_formation_effects
                            WHERE formation_job_id = :formation_job_id
                              AND organization_id = :organization_id
                              AND deleted IS FALSE
                            FOR UPDATE
                            """
                        ),
                        {
                            "formation_job_id": formation_job_id,
                            "organization_id": scope.organization_id,
                        },
                    )
                ).one_or_none()
                if effect is None:
                    raise MemoryError("Memory formation plan is unavailable.")
                if effect.finished_at is not None:
                    await self._guard_formation_commit()
                    return self._operations_from_outcomes(effect.outcomes)

                applied = await self._apply_plan(
                    session,
                    operations=operations,
                    vectors=vectors,
                    scope=scope,
                    source_conversation_id=source_conversation_id,
                    origin=origin,
                    actor=actor,
                    metadata=metadata,
                    formation_job_id=formation_job_id,
                )
                try:
                    await self._guard_formation_commit()
                except Exception as error:
                    guard_error = error
                    raise
                counts = MemoryOutcomeCounts.from_operations(applied)
                outcome_payload = {
                    "operations": [
                        operation.model_dump(mode="json") for operation in applied
                    ],
                    "counts": counts.model_dump(mode="json"),
                }
                await session.execute(
                    sql(
                        """
                        UPDATE memory_formation_effects
                        SET applied_flags = CAST(:applied_flags AS jsonb),
                            completed_count = :completed_count,
                            outcomes = CAST(:outcomes AS jsonb),
                            finished_at = now(), updated_at = now()
                        WHERE formation_job_id = :formation_job_id
                          AND organization_id = :organization_id
                          AND finished_at IS NULL
                        """
                    ),
                    {
                        "applied_flags": json.dumps(
                            [
                                operation.event is not MemoryEvent.NOOP
                                for operation in applied
                            ]
                        ),
                        "completed_count": len(applied),
                        "outcomes": json.dumps(outcome_payload),
                        "formation_job_id": formation_job_id,
                        "organization_id": scope.organization_id,
                    },
                )
                await session.commit()
                return applied
        except MemoryError:
            raise
        except Exception as error:
            if error is guard_error:
                raise
            logger.info("Memory formation plan rolled back: %s", type(error).__name__)
            raise MemoryError(
                "Memory formation plan conflicted with current facts.",
                vendor=PROVIDER,
                retryable=True,
            ) from None

    async def _guard_formation_commit(self) -> None:
        if self._before_formation_commit is not None:
            await self._before_formation_commit()

    async def _plan(
        self,
        messages: list[MemoryInputMessage],
        *,
        scope: MemoryScope,
    ) -> list[MemoryOperation]:
        query = self._related_query(messages)
        related = await self.search(query, scopes=(scope,), limit=RELATED_LIMIT)
        answer = await self._completer(
            system=EXTRACTION_SYSTEM_PROMPT,
            user=build_prompt(messages, related),
        )
        operations = parse_operations(answer, related, messages)
        self._validate_plan(operations)
        return operations

    async def _formation_plan(
        self,
        messages: list[MemoryInputMessage],
        *,
        scope: MemoryScope,
        formation_job_id: UUID,
    ) -> list[MemoryOperation]:
        stored = await self._stored_formation_plan(
            formation_job_id,
            scope.organization_id,
        )
        if stored is not None:
            return stored
        operations = await self._plan(messages, scope=scope)
        encoded = json.dumps(
            [operation.model_dump(mode="json") for operation in operations]
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql(
                    """
                    INSERT INTO memory_formation_effects
                        (id, organization_id, formation_job_id, operations,
                         applied_flags, completed_count, deleted, created_at,
                         updated_at)
                    SELECT gen_random_uuid(), :organization_id,
                           :formation_job_id, CAST(:operations AS jsonb),
                           CAST('[]' AS jsonb), 0, false, now(), now()
                    FROM memory_formation_jobs
                    WHERE id = :formation_job_id
                      AND organization_id = :organization_id
                      AND conversation_id = :conversation_id
                      AND deleted IS FALSE
                    ON CONFLICT (formation_job_id) DO NOTHING
                    """
                ),
                {
                    "organization_id": scope.organization_id,
                    "conversation_id": self._require_conversation_scope(scope),
                    "formation_job_id": formation_job_id,
                    "operations": encoded,
                },
            )
            await session.commit()
        stored = await self._stored_formation_plan(
            formation_job_id,
            scope.organization_id,
        )
        if stored is None:
            raise MemoryError("Memory formation plan was not persisted.")
        if result.rowcount not in {0, 1}:
            raise MemoryError("Memory formation plan persistence was ambiguous.")
        return stored

    async def _stored_formation_plan(
        self,
        formation_job_id: UUID,
        organization_id: UUID,
    ) -> list[MemoryOperation] | None:
        async with self._session_factory() as session:
            payload = await session.scalar(
                sql(
                    """
                    SELECT operations
                    FROM memory_formation_effects
                    WHERE formation_job_id = :formation_job_id
                      AND organization_id = :organization_id
                      AND deleted IS FALSE
                    """
                ),
                {
                    "formation_job_id": formation_job_id,
                    "organization_id": organization_id,
                },
            )
        if payload is None:
            return None
        if not isinstance(payload, list):
            raise MemoryError("Stored memory formation plan is invalid.")
        try:
            operations = [
                MemoryOperation.model_validate(operation) for operation in payload
            ]
        except (TypeError, ValidationError):
            raise MemoryError("Stored memory formation plan is invalid.") from None
        self._validate_plan(operations)
        return operations

    async def _completed_formation_result(
        self,
        formation_job_id: UUID,
        organization_id: UUID,
    ) -> list[MemoryOperation] | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    sql(
                        """
                        SELECT outcomes, finished_at
                        FROM memory_formation_effects
                        WHERE formation_job_id = :formation_job_id
                          AND organization_id = :organization_id
                          AND deleted IS FALSE
                        """
                    ),
                    {
                        "formation_job_id": formation_job_id,
                        "organization_id": organization_id,
                    },
                )
            ).one_or_none()
        if row is None or row.finished_at is None:
            return None
        return self._operations_from_outcomes(row.outcomes)

    @staticmethod
    def _operations_from_outcomes(payload: Any) -> list[MemoryOperation]:
        if not isinstance(payload, dict) or set(payload) != {"operations", "counts"}:
            raise MemoryError("Stored memory formation outcomes are invalid.")
        try:
            operations = [
                MemoryOperation.model_validate(operation)
                for operation in payload["operations"]
            ]
            counts = MemoryOutcomeCounts.model_validate(payload["counts"])
        except (TypeError, ValidationError):
            raise MemoryError("Stored memory formation outcomes are invalid.") from None
        if counts != MemoryOutcomeCounts.from_operations(operations):
            raise MemoryError("Stored memory formation counts are inconsistent.")
        return operations

    async def _operation_vectors(
        self,
        operations: list[MemoryOperation],
    ) -> dict[int, list[float]]:
        indexed_content = [
            (index, operation.content)
            for index, operation in enumerate(operations)
            if operation.event in {MemoryEvent.ADD, MemoryEvent.UPDATE}
        ]
        if not indexed_content:
            return {}
        vectors = await self._document_embedder(
            [content for _, content in indexed_content]
        )
        if len(vectors) != len(indexed_content):
            raise MemoryError(
                "Embedder returned an invalid memory vector count.",
                vendor=PROVIDER,
            )
        dimensions = self._embedding_space.dimensions
        if any(len(vector) != dimensions for vector in vectors):
            raise MemoryError(
                "Embedder returned invalid memory vector dimensions.",
                vendor=PROVIDER,
            )
        return {
            index: vector
            for (index, _content), vector in zip(indexed_content, vectors, strict=True)
        }

    async def _apply_plan(
        self,
        session,
        *,
        operations: list[MemoryOperation],
        vectors: dict[int, list[float]],
        scope: MemoryScope,
        source_conversation_id: UUID,
        origin: MemoryOrigin,
        actor: MemoryActor | None,
        metadata: dict[str, Any] | None,
        formation_job_id: UUID | None,
    ) -> list[MemoryOperation]:
        self._validate_plan(operations)
        await self._lock_active_embedding_space(session)
        scope_clause, scope_params = self._scope_sql(scope)
        target_ids = [
            operation.target_id
            for operation in operations
            if operation.target_id is not None
        ]
        targets: dict[UUID, Any] = {}
        if target_ids:
            rows = await session.execute(
                sql(
                    f"""
                    SELECT id, content, content_hash, state_revision
                    FROM memory_memories
                    WHERE id = ANY(CAST(:target_ids AS uuid[]))
                      AND {scope_clause}
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND deleted IS FALSE
                    FOR UPDATE
                    """
                ),
                {
                    "target_ids": target_ids,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            targets = {row.id: row for row in rows}
            if set(targets) != set(target_ids):
                raise MemoryError(
                    "Memory plan target changed before commit.",
                    vendor=PROVIDER,
                    retryable=True,
                )

        proposed_hashes = [
            _digest(operation.content)
            for operation in operations
            if operation.event in {MemoryEvent.ADD, MemoryEvent.UPDATE}
        ]
        existing_by_hash: dict[str, _FactSnapshot] = {}
        if proposed_hashes:
            rows = await session.execute(
                sql(
                    f"""
                    SELECT id, content, content_hash, state_revision,
                           expires_at IS NOT NULL AND expires_at <= now()
                               AS expired
                    FROM memory_memories
                    WHERE content_hash = ANY(CAST(:content_hashes AS text[]))
                      AND {scope_clause}
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND deleted IS FALSE
                    FOR UPDATE
                    """
                ),
                {
                    "content_hashes": proposed_hashes,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            existing_by_hash = {
                row.content_hash: _FactSnapshot(
                    id=row.id,
                    content=row.content,
                    state_revision=row.state_revision,
                    expired=row.expired,
                )
                for row in rows
            }

        applied: list[MemoryOperation] = []
        for index, operation in enumerate(operations):
            if operation.event is MemoryEvent.NOOP:
                applied.append(operation)
                continue
            provenance = self._provenance(
                operation,
                source_conversation_id=source_conversation_id,
                origin=origin,
                actor=actor,
                formation_job_id=formation_job_id,
            )
            if operation.event is MemoryEvent.ADD:
                content_hash = _digest(operation.content)
                duplicate = existing_by_hash.get(content_hash)
                if duplicate is not None:
                    if duplicate.expired:
                        vector = vectors.get(index)
                        if vector is None:
                            raise MemoryError("Memory reactivation has no embedding.")
                        committed = await self._reactivate(
                            session,
                            operation=operation,
                            memory_id=duplicate.id,
                            expected_state_revision=duplicate.state_revision,
                            vector=vector,
                            scope=scope,
                            provenance=provenance,
                            metadata=metadata,
                            formation_job_id=formation_job_id,
                            formation_operation_index=(
                                index if formation_job_id is not None else None
                            ),
                        )
                        existing_by_hash[content_hash] = _FactSnapshot(
                            id=duplicate.id,
                            content=operation.content,
                            state_revision=duplicate.state_revision + 1,
                            expired=False,
                        )
                        applied.append(committed)
                        continue
                    applied.append(
                        MemoryOperation(
                            event=MemoryEvent.NOOP,
                            content=operation.content,
                            target_id=duplicate.id,
                            previous=duplicate.content,
                            source_messages=operation.source_messages,
                        )
                    )
                    continue
                vector = vectors.get(index)
                if vector is None:
                    raise MemoryError("Memory ADD has no embedding.")
                memory_id = (
                    uuid5(formation_job_id, f"operation:{index}")
                    if formation_job_id is not None
                    else uuid4()
                )
                await session.execute(
                    sql(
                        """
                        INSERT INTO memory_memories
                            (id, organization_id, external_id, scope_level,
                             agent_id, contact_id, conversation_id,
                             source_conversation_id,
                             content, content_hash, meta, provenance, state_revision,
                             embedding, memory_provider_config_id,
                             memory_provider_config_revision,
                             embedding_provider_config_id,
                             embedding_provider_config_revision,
                             embedding_provider, embedding_endpoint, embedding_model,
                             embedding_dimensions, embedding_semantic_options,
                             embedding_space_id, deleted,
                             created_at, updated_at)
                        VALUES
                            (:id, :organization_id, gen_random_uuid()::text,
                             CAST(:scope_level AS memory_level_enum),
                             :agent_id, :contact_id, :conversation_id,
                             :source_conversation_id, :content, :content_hash,
                             CAST(:meta AS jsonb), CAST(:provenance AS jsonb), 1,
                             CAST(:embedding AS vector),
                             :memory_provider_config_id,
                             :memory_provider_config_revision,
                             :embedding_provider_config_id,
                             :embedding_provider_config_revision,
                             :embedding_provider, :embedding_endpoint,
                             :embedding_model, :embedding_dimensions,
                             CAST(:embedding_semantic_options AS jsonb),
                             :embedding_space_id, false, now(), now())
                        """
                    ),
                    {
                        "id": memory_id,
                        **self._scope_owner_params(scope),
                        "source_conversation_id": provenance.source_conversation_id,
                        "content": operation.content,
                        "content_hash": content_hash,
                        "meta": json.dumps(metadata or {}),
                        "provenance": provenance.model_dump_json(),
                        "embedding": _vector(vector),
                        **self._authority_params(),
                    },
                )
                await self._record(
                    session,
                    memory_id,
                    scope,
                    MemoryEvent.ADD,
                    None,
                    operation.content,
                    provenance,
                    memory_state_revision=1,
                    formation_job_id=formation_job_id,
                    formation_operation_index=(
                        index if formation_job_id is not None else None
                    ),
                )
                existing_by_hash[content_hash] = _FactSnapshot(
                    id=memory_id,
                    content=operation.content,
                    state_revision=1,
                    expired=False,
                )
                applied.append(operation.model_copy(update={"target_id": memory_id}))
                continue

            target = targets[operation.target_id]
            if operation.event is MemoryEvent.UPDATE:
                content_hash = _digest(operation.content)
                if content_hash == target.content_hash:
                    applied.append(
                        MemoryOperation(
                            event=MemoryEvent.NOOP,
                            content=operation.content,
                            target_id=target.id,
                            previous=target.content,
                            source_messages=operation.source_messages,
                        )
                    )
                    continue
                duplicate = existing_by_hash.get(content_hash)
                if duplicate is not None and duplicate.id != target.id:
                    raise MemoryError(
                        "Memory update would duplicate another fact.",
                        vendor=PROVIDER,
                    )
                vector = vectors.get(index)
                if vector is None:
                    raise MemoryError("Memory UPDATE has no embedding.")
                result = await session.execute(
                    sql(
                        f"""
                        UPDATE memory_memories
                        SET content = :content, content_hash = :content_hash,
                            source_conversation_id = :source_conversation_id,
                            provenance = CAST(:provenance AS jsonb),
                            embedding = CAST(:embedding AS vector),
                            state_revision = state_revision + 1, updated_at = now()
                        WHERE id = :id
                          AND {scope_clause}
                          AND state_revision = :expected_state_revision
                          AND memory_provider_config_id = :memory_provider_config_id
                          AND embedding_space_id = :embedding_space_id
                          AND deleted IS FALSE
                        """
                    ),
                    {
                        "id": target.id,
                        "content": operation.content,
                        "content_hash": content_hash,
                        "source_conversation_id": provenance.source_conversation_id,
                        "provenance": provenance.model_dump_json(),
                        "embedding": _vector(vector),
                        "expected_state_revision": target.state_revision,
                        **scope_params,
                        **self._memory_config_params(),
                        "embedding_space_id": self._embedding_space.id,
                    },
                )
                if result.rowcount != 1:
                    raise MemoryError(
                        "Memory update lost its state revision.",
                        retryable=True,
                    )
                committed = operation.model_copy(update={"previous": target.content})
                await self._record(
                    session,
                    target.id,
                    scope,
                    MemoryEvent.UPDATE,
                    target.content,
                    operation.content,
                    provenance,
                    memory_state_revision=target.state_revision + 1,
                    formation_job_id=formation_job_id,
                    formation_operation_index=(
                        index if formation_job_id is not None else None
                    ),
                )
                existing_by_hash.pop(target.content_hash, None)
                existing_by_hash[content_hash] = _FactSnapshot(
                    id=target.id,
                    content=operation.content,
                    state_revision=target.state_revision + 1,
                    expired=False,
                )
                applied.append(committed)
                continue

            result = await session.execute(
                sql(
                    f"""
                    DELETE FROM memory_memories
                    WHERE id = :id
                      AND {scope_clause}
                      AND state_revision = :expected_state_revision
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                    """
                ),
                {
                    "id": target.id,
                    "expected_state_revision": target.state_revision,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            if result.rowcount != 1:
                raise MemoryError(
                    "Memory delete lost its state revision.",
                    retryable=True,
                )
            await self._record(
                session,
                target.id,
                scope,
                MemoryEvent.DELETE,
                None,
                None,
                provenance,
                memory_state_revision=target.state_revision + 1,
                formation_job_id=formation_job_id,
                formation_operation_index=(
                    index if formation_job_id is not None else None
                ),
            )
            existing_by_hash.pop(target.content_hash, None)
            applied.append(operation)
        return applied

    async def _reactivate(
        self,
        session,
        *,
        operation: MemoryOperation,
        memory_id: UUID,
        expected_state_revision: int,
        vector: list[float],
        scope: MemoryScope,
        provenance: MemoryProvenance,
        metadata: dict[str, Any] | None,
        formation_job_id: UUID | None,
        formation_operation_index: int | None,
    ) -> MemoryOperation:
        """Make one exact expired fact active again without losing identity."""
        scope_clause, scope_params = self._scope_sql(scope)
        result = await session.execute(
            sql(
                f"""
                UPDATE memory_memories
                SET source_conversation_id = :source_conversation_id,
                    meta = CAST(:meta AS jsonb),
                    provenance = CAST(:provenance AS jsonb),
                    embedding = CAST(:embedding AS vector),
                    expires_at = NULL,
                    state_revision = state_revision + 1,
                    updated_at = now()
                WHERE id = :id
                  AND {scope_clause}
                  AND state_revision = :expected_state_revision
                  AND memory_provider_config_id = :memory_provider_config_id
                  AND embedding_space_id = :embedding_space_id
                  AND deleted IS FALSE
                  AND expires_at IS NOT NULL
                  AND expires_at <= now()
                """
            ),
            {
                "id": memory_id,
                "source_conversation_id": provenance.source_conversation_id,
                "meta": json.dumps(metadata or {}),
                "provenance": provenance.model_dump_json(),
                "embedding": _vector(vector),
                "expected_state_revision": expected_state_revision,
                **scope_params,
                **self._memory_config_params(),
                "embedding_space_id": self._embedding_space.id,
            },
        )
        if result.rowcount != 1:
            raise MemoryError(
                "Memory reactivation lost its state revision.",
                retryable=True,
            )
        await self._record(
            session,
            memory_id,
            scope,
            MemoryEvent.ADD,
            None,
            operation.content,
            provenance,
            memory_state_revision=expected_state_revision + 1,
            formation_job_id=formation_job_id,
            formation_operation_index=formation_operation_index,
        )
        return operation.model_copy(update={"target_id": memory_id})

    @staticmethod
    def _validate_plan(operations: list[MemoryOperation]) -> None:
        if len(operations) > MEMORY_MAX_OPERATIONS:
            raise MemoryError("Memory operation plan exceeds its limit.")
        targets: set[UUID] = set()
        proposed_hashes: set[str] = set()
        for operation in operations:
            if operation.event in {MemoryEvent.ADD, MemoryEvent.UPDATE}:
                if require_memory_fact(operation.content) != operation.content:
                    raise MemoryError(
                        "Memory operation fact is not canonically normalized."
                    )
                content_hash = _digest(operation.content)
                if content_hash in proposed_hashes:
                    raise MemoryError("Memory operation plan repeats fact content.")
                proposed_hashes.add(content_hash)
            if operation.event in {MemoryEvent.UPDATE, MemoryEvent.DELETE}:
                if operation.target_id is None:
                    raise MemoryError("Memory operation plan omitted a target.")
                if operation.target_id in targets:
                    raise MemoryError("Memory operation plan repeats a target.")
                targets.add(operation.target_id)
            elif operation.event is MemoryEvent.ADD and operation.target_id is not None:
                raise MemoryError("Memory ADD operation has an unexpected target.")
            if (
                operation.event is not MemoryEvent.NOOP
                and not operation.source_messages
            ):
                raise MemoryError("Memory operation plan omitted source evidence.")

    @staticmethod
    def _related_query(messages: list[MemoryInputMessage]) -> str:
        if not messages:
            raise MemoryError("Memory exchange is empty.")
        for message in reversed(messages):
            if message.role.value == "user":
                return require_memory_query(message.content)
        return require_memory_query(messages[-1].content)

    # ---- retrieval ---------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        scopes: tuple[MemoryScope, ...],
        limit: int = 5,
    ) -> list[MemoryResult]:
        normalized_query = require_memory_query(query)
        self._validate_result_limit(limit)

        vector = await self._query_embedder(normalized_query)
        if len(vector) != self._embedding_space.dimensions:
            raise MemoryError("Memory query embedding dimensions are invalid.")

        clauses, params = self._scopes_sql(scopes)
        params.update(
            {
                "embedding": _vector(vector),
                "embedding_space_id": self._embedding_space.id,
                "limit": limit,
                **self._memory_config_params(),
            }
        )

        async with self._session_factory() as session:
            await self._lock_active_embedding_space(session)
            rows = await session.execute(
                sql(
                    f"""
                    SELECT id, content, scope_level, agent_id, contact_id,
                           conversation_id, organization_id,
                           meta, provenance, updated_at,
                           embedding <=> CAST(:embedding AS vector) AS distance
                    FROM memory_memories
                    WHERE deleted IS FALSE AND embedding IS NOT NULL
                      AND (expires_at IS NULL OR expires_at > now())
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND {clauses}
                    ORDER BY distance ASC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [
                MemoryResult(
                    id=row.id,
                    content=row.content,
                    # Inverted so higher is better, matching every other socket.
                    score=1.0 - float(row.distance),
                    scope=self._scope_of(row),
                    updated_at=row.updated_at,
                    metadata=row.meta or {},
                    provenance=MemoryProvenance.model_validate(row.provenance),
                )
                for row in rows
            ]

    async def get_all(self, *, scope: MemoryScope, limit: int = 100) -> list[Memory]:
        self._validate_result_limit(limit)
        clauses, params = self._scope_sql(scope)
        params.update(
            {
                "embedding_space_id": self._embedding_space.id,
                "limit": limit,
                **self._memory_config_params(),
            }
        )
        async with self._session_factory() as session:
            await self._lock_active_embedding_space(session)
            rows = await session.execute(
                sql(
                    f"""
                    SELECT id, content, scope_level, agent_id, contact_id,
                           conversation_id, organization_id,
                           meta, provenance, created_at, updated_at
                    FROM memory_memories
                    WHERE deleted IS FALSE
                      AND (expires_at IS NULL OR expires_at > now())
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND {clauses}
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [
                Memory(
                    id=row.id,
                    content=row.content,
                    scope=self._scope_of(row),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    metadata=row.meta or {},
                    provenance=MemoryProvenance.model_validate(row.provenance),
                )
                for row in rows
            ]

    @staticmethod
    def _validate_result_limit(limit: int) -> None:
        if isinstance(limit, bool) or not 1 <= limit <= MEMORY_MAX_SEARCH_RESULTS:
            raise MemoryError("Memory result limit is outside its bounds.")

    # ---- correction and erasure --------------------------------------

    async def update(
        self,
        memory_id: UUID,
        content: str,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> MemoryUpdateResult:
        normalized = require_memory_fact(content)
        content_hash = _digest(normalized)
        scope_clause, scope_params = self._scope_sql(scope)

        async with self._session_factory() as session:
            current = await self._locked_memory(session, memory_id, scope)
            if current is None:
                raise MemoryError("That memory is gone.", vendor=PROVIDER)
            if current.content_hash == content_hash:
                memory = self._memory_of(current)
                await session.rollback()
                return MemoryUpdateResult(memory=memory, changed=False)
            await session.rollback()

        vectors = await self._document_embedder([normalized])
        if len(vectors) != 1 or len(vectors[0]) != self._embedding_space.dimensions:
            raise MemoryError("Memory correction embedding is invalid.")
        async with self._session_factory() as session:
            current = await self._locked_memory(session, memory_id, scope)
            if current is None:
                raise MemoryError("That memory is gone.", vendor=PROVIDER)
            if current.content_hash == content_hash:
                memory = self._memory_of(current)
                await session.rollback()
                return MemoryUpdateResult(memory=memory, changed=False)
            duplicate = await session.scalar(
                sql(
                    f"""
                    SELECT id FROM memory_memories
                    WHERE content_hash = :content_hash
                      AND id <> :id
                      AND {scope_clause}
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND deleted IS FALSE
                    FOR UPDATE
                    """
                ),
                {
                    "id": memory_id,
                    "content_hash": content_hash,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            if duplicate is not None:
                raise MemoryError("Memory correction duplicates another fact.")
            row = (
                await session.execute(
                    sql(
                        f"""
                        UPDATE memory_memories
                        SET content = :content, content_hash = :content_hash,
                            source_conversation_id = COALESCE(
                                :source_conversation_id,
                                source_conversation_id
                            ),
                            provenance = CAST(:provenance AS jsonb),
                            embedding = CAST(:embedding AS vector),
                            state_revision = state_revision + 1, updated_at = now()
                        WHERE id = :id
                          AND {scope_clause}
                          AND state_revision = :expected_state_revision
                          AND memory_provider_config_id = :memory_provider_config_id
                          AND embedding_space_id = :embedding_space_id
                          AND deleted IS FALSE
                          AND (expires_at IS NULL OR expires_at > now())
                        RETURNING id, content, scope_level, agent_id, contact_id,
                                  conversation_id, organization_id,
                                  meta, provenance, created_at, updated_at
                        """
                    ),
                    {
                        "id": memory_id,
                        "content": normalized,
                        "content_hash": content_hash,
                        "source_conversation_id": provenance.source_conversation_id,
                        "provenance": provenance.model_dump_json(),
                        "embedding": _vector(vectors[0]),
                        "expected_state_revision": current.state_revision,
                        **scope_params,
                        **self._memory_config_params(),
                        "embedding_space_id": self._embedding_space.id,
                    },
                )
            ).one_or_none()
            if row is None:
                raise MemoryError(
                    "Memory correction lost its state revision.",
                    retryable=True,
                )
            await self._record(
                session,
                memory_id,
                scope,
                MemoryEvent.UPDATE,
                current.content,
                normalized,
                provenance,
                memory_state_revision=current.state_revision + 1,
            )
            await session.commit()
        return MemoryUpdateResult(
            memory=self._memory_of(row),
            changed=True,
        )

    async def expire(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> bool:
        """Expire one active fact without deleting its content or history."""
        scope_clause, scope_params = self._scope_sql(scope)
        async with self._session_factory() as session:
            current = await self._locked_memory(session, memory_id, scope)
            if current is None:
                await session.rollback()
                return False
            result = await session.execute(
                sql(
                    f"""
                    UPDATE memory_memories
                    SET expires_at = now(),
                        source_conversation_id = COALESCE(
                            :source_conversation_id,
                            source_conversation_id
                        ),
                        provenance = CAST(:provenance AS jsonb),
                        state_revision = state_revision + 1,
                        updated_at = now()
                    WHERE id = :id
                      AND {scope_clause}
                      AND state_revision = :expected_state_revision
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND deleted IS FALSE
                      AND (expires_at IS NULL OR expires_at > now())
                    """
                ),
                {
                    "id": memory_id,
                    "source_conversation_id": provenance.source_conversation_id,
                    "provenance": provenance.model_dump_json(),
                    "expected_state_revision": current.state_revision,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            if result.rowcount != 1:
                raise MemoryError(
                    "Memory expiry lost its state revision.",
                    retryable=True,
                )
            await self._record(
                session,
                memory_id,
                scope,
                MemoryEvent.EXPIRE,
                current.content,
                None,
                provenance,
                memory_state_revision=current.state_revision + 1,
            )
            await session.commit()
            return True

    async def delete(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> bool:
        """Delete the scoped current fact/vector and append a content-free event."""
        scope_clause, scope_params = self._scope_sql(scope)
        async with self._session_factory() as session:
            current = await self._locked_memory(
                session,
                memory_id,
                scope,
                include_expired=True,
            )
            if current is None:
                await session.rollback()
                return False
            result = await session.execute(
                sql(
                    "DELETE FROM memory_memories WHERE id = :id AND "
                    f"{scope_clause} "
                    "AND state_revision = :expected_state_revision "
                    "AND memory_provider_config_id = :memory_provider_config_id "
                    "AND embedding_space_id = :embedding_space_id"
                ),
                {
                    "id": memory_id,
                    **scope_params,
                    "expected_state_revision": current.state_revision,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
            if result.rowcount != 1:
                raise MemoryError(
                    "Memory deletion lost its state revision.",
                    retryable=True,
                )
            await self._record(
                session,
                memory_id,
                scope,
                MemoryEvent.DELETE,
                None,
                None,
                provenance,
                memory_state_revision=current.state_revision + 1,
            )
            await session.commit()
            return True

    async def history(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
    ) -> list[MemoryChange]:
        scope_clause, scope_params = self._scope_sql(scope)
        async with self._session_factory() as session:
            rows = await session.execute(
                sql(
                    f"""
                    SELECT id, memory_id, organization_id, scope_level,
                           agent_id, contact_id, conversation_id,
                           event, before, after, provenance, created_at
                    FROM memory_changes
                    WHERE memory_id = :id
                      AND {scope_clause}
                    ORDER BY created_at ASC
                    """
                ),
                {
                    "id": memory_id,
                    **scope_params,
                },
            )
            return [
                MemoryChange(
                    id=row.id,
                    memory_id=row.memory_id,
                    event=MemoryEvent(row.event),
                    before=row.before,
                    after=row.after,
                    created_at=row.created_at,
                    scope=self._scope_of(row),
                    provenance=MemoryProvenance.model_validate(row.provenance),
                )
                for row in rows
            ]

    # ---- internals ---------------------------------------------------

    async def _record(
        self,
        session,
        memory_id: UUID,
        scope: MemoryScope,
        event: MemoryEvent,
        before: str | None,
        after: str | None,
        provenance: MemoryProvenance,
        *,
        memory_state_revision: int,
        formation_job_id: UUID | None = None,
        formation_operation_index: int | None = None,
        reconciliation_operation_index: int | None = None,
    ) -> None:
        change_id = uuid4()
        inserted = (
            await session.execute(
                sql(
                    """
                INSERT INTO memory_changes
                    (id, memory_id, organization_id, scope_level,
                     agent_id, contact_id, conversation_id,
                     source_conversation_id, event,
                     before, after, provenance, memory_state_revision,
                     memory_provider_config_id,
                     memory_provider_config_revision,
                     embedding_provider_config_id,
                     embedding_provider_config_revision,
                     embedding_provider, embedding_endpoint, embedding_model,
                     embedding_dimensions, embedding_semantic_options,
                     embedding_space_id,
                     reconciliation_llm_provider_config_id,
                     reconciliation_llm_provider_config_revision,
                     reconciliation_llm_provider, reconciliation_llm_model,
                     reconciliation_prompt_revision,
                     formation_job_id, formation_operation_index,
                     reconciliation_job_id, reconciliation_operation_index, deleted,
                     created_at, updated_at)
                VALUES
                    (:change_id, :memory_id, :organization_id,
                     CAST(:scope_level AS memory_level_enum),
                     :agent_id, :contact_id, :conversation_id,
                     :source_conversation_id, CAST(:event AS memory_event_enum),
                     :before, :after, CAST(:provenance AS jsonb),
                     :memory_state_revision, :memory_provider_config_id,
                     :memory_provider_config_revision,
                     :embedding_provider_config_id,
                     :embedding_provider_config_revision,
                     :embedding_provider, :embedding_endpoint, :embedding_model,
                     :embedding_dimensions,
                     CAST(:embedding_semantic_options AS jsonb),
                     :embedding_space_id,
                     :reconciliation_llm_provider_config_id,
                     :reconciliation_llm_provider_config_revision,
                     :reconciliation_llm_provider, :reconciliation_llm_model,
                     :reconciliation_prompt_revision,
                     :formation_job_id, :formation_operation_index,
                     :reconciliation_job_id, :reconciliation_operation_index,
                     false, now(), now())
                RETURNING created_at
                    """
                ),
                {
                    "change_id": change_id,
                    "memory_id": memory_id,
                    **self._scope_owner_params(scope),
                    "source_conversation_id": provenance.source_conversation_id,
                    "event": event.value,
                    "before": before,
                    "after": after,
                    "provenance": provenance.model_dump_json(),
                    "memory_state_revision": memory_state_revision,
                    **self._authority_params(),
                    **self._reconciliation_authority_params(),
                    "formation_job_id": formation_job_id,
                    "formation_operation_index": formation_operation_index,
                    "reconciliation_job_id": provenance.reconciliation_job_id,
                    "reconciliation_operation_index": (
                        reconciliation_operation_index
                    ),
                },
            )
        ).one()
        await session.execute(
            sql(
                """
                INSERT INTO memory_reconciliation_cursors
                    (id, organization_id, scope_level, owner_id,
                     agent_id, contact_id, conversation_id,
                     memory_provider_config_id,
                     memory_provider_config_revision,
                     embedding_provider_config_id,
                     embedding_provider_config_revision,
                     embedding_provider, embedding_endpoint, embedding_model,
                     embedding_dimensions, embedding_semantic_options,
                     embedding_space_id,
                     reconciliation_llm_provider_config_id,
                     reconciliation_llm_provider_config_revision,
                     reconciliation_llm_provider, reconciliation_llm_model,
                     reconciliation_prompt_revision,
                     requested_through_created_at, requested_through_change_id,
                     next_generation, deleted, created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :organization_id,
                     CAST(:scope_level AS memory_level_enum), :owner_id,
                     :agent_id, :contact_id, :conversation_id,
                     :memory_provider_config_id,
                     :memory_provider_config_revision,
                     :embedding_provider_config_id,
                     :embedding_provider_config_revision,
                     :embedding_provider, :embedding_endpoint, :embedding_model,
                     :embedding_dimensions,
                     CAST(:embedding_semantic_options AS jsonb),
                     :embedding_space_id,
                     :reconciliation_llm_provider_config_id,
                     :reconciliation_llm_provider_config_revision,
                     :reconciliation_llm_provider, :reconciliation_llm_model,
                     :reconciliation_prompt_revision,
                     :requested_at, :change_id, 1, false, now(), now())
                ON CONFLICT
                    (organization_id, memory_provider_config_id,
                     scope_level, owner_id)
                DO UPDATE SET
                    memory_provider_config_revision =
                        EXCLUDED.memory_provider_config_revision,
                    embedding_provider_config_id =
                        EXCLUDED.embedding_provider_config_id,
                    embedding_provider_config_revision =
                        EXCLUDED.embedding_provider_config_revision,
                    embedding_provider = EXCLUDED.embedding_provider,
                    embedding_endpoint = EXCLUDED.embedding_endpoint,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    embedding_semantic_options =
                        EXCLUDED.embedding_semantic_options,
                    embedding_space_id = EXCLUDED.embedding_space_id,
                    reconciliation_llm_provider_config_id =
                        EXCLUDED.reconciliation_llm_provider_config_id,
                    reconciliation_llm_provider_config_revision =
                        EXCLUDED.reconciliation_llm_provider_config_revision,
                    reconciliation_llm_provider =
                        EXCLUDED.reconciliation_llm_provider,
                    reconciliation_llm_model =
                        EXCLUDED.reconciliation_llm_model,
                    reconciliation_prompt_revision =
                        EXCLUDED.reconciliation_prompt_revision,
                    active_job_id = CASE
                        WHEN memory_reconciliation_cursors.active_job_id IS NOT NULL
                         AND EXISTS (
                            SELECT 1
                            FROM memory_reconciliation_jobs AS active_job
                            WHERE active_job.id =
                                memory_reconciliation_cursors.active_job_id
                              AND active_job.organization_id =
                                memory_reconciliation_cursors.organization_id
                              AND active_job.state = 'failed'
                              AND active_job.deleted IS FALSE
                         )
                        THEN NULL
                        ELSE memory_reconciliation_cursors.active_job_id
                    END,
                    requested_through_created_at =
                        EXCLUDED.requested_through_created_at,
                    requested_through_change_id =
                        EXCLUDED.requested_through_change_id,
                    updated_at = now()
                WHERE ROW(
                    memory_reconciliation_cursors.requested_through_created_at,
                    memory_reconciliation_cursors.requested_through_change_id
                ) < ROW(
                    EXCLUDED.requested_through_created_at,
                    EXCLUDED.requested_through_change_id
                )
                """
            ),
            {
                **self._scope_owner_params(scope),
                "owner_id": scope.owner_id,
                "change_id": change_id,
                "requested_at": inserted.created_at,
                **self._authority_params(),
                **self._reconciliation_authority_params(),
            },
        )

    async def _locked_memory(
        self,
        session,
        memory_id: UUID,
        scope: MemoryScope,
        *,
        include_expired: bool = False,
    ):
        await self._lock_active_embedding_space(session)
        scope_clause, scope_params = self._scope_sql(scope)
        expiry_clause = "" if include_expired else "AND (expires_at IS NULL OR expires_at > now())"
        return (
            await session.execute(
                sql(
                    f"""
                    SELECT id, content, content_hash, state_revision,
                           scope_level, agent_id, contact_id, conversation_id,
                           organization_id, meta, provenance,
                           created_at, updated_at
                    FROM memory_memories
                    WHERE id = :id
                      AND {scope_clause}
                      AND memory_provider_config_id = :memory_provider_config_id
                      AND embedding_space_id = :embedding_space_id
                      AND deleted IS FALSE
                      {expiry_clause}
                    FOR UPDATE
                    """
                ),
                {
                    "id": memory_id,
                    **scope_params,
                    **self._memory_config_params(),
                    "embedding_space_id": self._embedding_space.id,
                },
            )
        ).one_or_none()

    async def _lock_active_embedding_space(self, session) -> None:
        active_space_id = await session.scalar(
            sql(
                """
                SELECT embedding_space_id
                FROM memory_indexes
                WHERE organization_id = :organization_id
                  AND memory_provider_config_id = :memory_provider_config_id
                  AND deleted IS FALSE
                FOR SHARE
                """
            ),
            {
                "organization_id": self._embedding_space.organization_id,
                **self._memory_config_params(),
            },
        )
        if active_space_id is None:
            raise MemoryError(
                "Memory embedding index is unavailable.",
                vendor=PROVIDER,
            )
        if active_space_id != self._embedding_space.id:
            raise MemoryError(
                "Memory embedding index changed; resolve a fresh adapter.",
                vendor=PROVIDER,
                retryable=True,
            )

    def _embedding_params(self) -> dict[str, object]:
        space = self._embedding_space
        return {
            "embedding_provider_config_id": space.provider_config_id,
            "embedding_provider_config_revision": space.provider_config_revision,
            "embedding_provider": space.provider,
            "embedding_endpoint": space.endpoint,
            "embedding_model": space.model,
            "embedding_dimensions": space.dimensions,
            "embedding_semantic_options": json.dumps(space.semantic_options),
            "embedding_space_id": space.id,
        }

    def _memory_authority_params(self) -> dict[str, object]:
        return {
            **self._memory_config_params(),
            "memory_provider_config_revision": self._memory_provider_config_revision,
        }

    def _memory_config_params(self) -> dict[str, object]:
        return {"memory_provider_config_id": self._memory_provider_config_id}

    def _authority_params(self) -> dict[str, object]:
        return {**self._memory_authority_params(), **self._embedding_params()}

    def _reconciliation_authority_params(self) -> dict[str, object]:
        authority = self._extraction_authority
        return {
            "reconciliation_llm_provider_config_id": authority.provider_config_id,
            "reconciliation_llm_provider_config_revision": (
                authority.provider_config_revision
            ),
            "reconciliation_llm_provider": authority.provider,
            "reconciliation_llm_model": authority.model,
            "reconciliation_prompt_revision": RECONCILIATION_PROMPT_REVISION,
        }

    @classmethod
    def _scope_sql(cls, scope: MemoryScope) -> tuple[str, dict[str, object]]:
        """Return one exact scope predicate from a fixed field mapping."""
        owner_column = cls._owner_column(scope.level)
        return (
            "organization_id = :organization_id "
            "AND scope_level = CAST(:scope_level AS memory_level_enum) "
            f"AND {owner_column} = :scope_owner_id",
            {
                "organization_id": scope.organization_id,
                "scope_level": scope.level.value,
                "scope_owner_id": scope.owner_id,
            },
        )

    @classmethod
    def _scopes_sql(
        cls,
        scopes: tuple[MemoryScope, ...],
    ) -> tuple[str, dict[str, object]]:
        if not scopes or len(scopes) > len(MemoryLevel):
            raise MemoryError("Memory recall scope set is invalid.")
        organization_id = scopes[0].organization_id
        if any(scope.organization_id != organization_id for scope in scopes):
            raise MemoryError("Memory recall scopes cross organizations.")
        if len(set(scopes)) != len(scopes):
            raise MemoryError("Memory recall scopes repeat an owner.")

        predicates = []
        params: dict[str, object] = {"organization_id": organization_id}
        for index, scope in enumerate(scopes):
            level_key = f"scope_level_{index}"
            owner_key = f"scope_owner_id_{index}"
            predicates.append(
                "(scope_level = "
                f"CAST(:{level_key} AS memory_level_enum) AND "
                f"{cls._owner_column(scope.level)} = :{owner_key})"
            )
            params[level_key] = scope.level.value
            params[owner_key] = scope.owner_id
        return (
            "organization_id = :organization_id AND ("
            + " OR ".join(predicates)
            + ")",
            params,
        )

    @staticmethod
    def _owner_column(level: MemoryLevel) -> str:
        return {
            MemoryLevel.AGENT: "agent_id",
            MemoryLevel.USER: "contact_id",
            MemoryLevel.CONVERSATION: "conversation_id",
        }[level]

    @staticmethod
    def _scope_owner_params(scope: MemoryScope) -> dict[str, object]:
        return {
            "organization_id": scope.organization_id,
            "scope_level": scope.level.value,
            "agent_id": scope.owner_id if scope.level is MemoryLevel.AGENT else None,
            "contact_id": scope.owner_id if scope.level is MemoryLevel.USER else None,
            "conversation_id": (
                scope.owner_id if scope.level is MemoryLevel.CONVERSATION else None
            ),
        }

    @staticmethod
    def _scope_of(row) -> MemoryScope:
        level = MemoryLevel(row.scope_level)
        owner_id = {
            MemoryLevel.AGENT: row.agent_id,
            MemoryLevel.USER: row.contact_id,
            MemoryLevel.CONVERSATION: row.conversation_id,
        }[level]
        if owner_id is None:
            raise MemoryError("Stored memory scope is incomplete.", vendor=PROVIDER)
        return MemoryScope(
            organization_id=row.organization_id,
            level=level,
            owner_id=owner_id,
        )

    def _memory_of(self, row) -> Memory:
        return Memory(
            id=row.id,
            content=row.content,
            scope=self._scope_of(row),
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=row.meta or {},
            provenance=MemoryProvenance.model_validate(row.provenance),
        )

    @staticmethod
    def _require_conversation_scope(scope: MemoryScope) -> UUID:
        if scope.level is not MemoryLevel.CONVERSATION:
            raise MemoryError("Durable formation requires Conversation memory.")
        return scope.owner_id

    def _provenance(
        self,
        operation: MemoryOperation,
        *,
        source_conversation_id: UUID,
        origin: MemoryOrigin,
        actor: MemoryActor | None,
        formation_job_id: UUID | None,
    ) -> MemoryProvenance:
        return MemoryProvenance(
            origin=origin,
            source_conversation_id=source_conversation_id,
            source_messages=operation.source_messages,
            actor=actor,
            formation_job_id=formation_job_id,
            extraction=self._extraction_authority,
        )
