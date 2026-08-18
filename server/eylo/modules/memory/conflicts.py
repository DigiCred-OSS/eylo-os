"""Read current revision-fenced conflict evidence for authorized recall scopes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import aliased

from eylo.common.contracts.memory import (
    MemoryConflictEvidence,
    MemoryConflictFact,
    MemoryError,
    MemoryScope,
)
from eylo.common.contracts.memory_reconciliation import MemoryRelationshipKind
from eylo.modules.memory.models import MemoryModel, MemoryRelationshipModel
from eylo.modules.memory.service import memory_owner_id

MAX_RECALLED_CONFLICTS = 10


class MemoryConflictReader:
    """Project only current conflicts touching the recalled result set."""

    def __init__(self, session) -> None:
        self._session = session

    async def for_recalled(
        self,
        *,
        organization_id: UUID,
        scopes: tuple[MemoryScope, ...],
        memory_ids: list[UUID],
        limit: int = MAX_RECALLED_CONFLICTS,
    ) -> list[MemoryConflictEvidence]:
        selected_ids = set(memory_ids)
        if not selected_ids or not scopes:
            return []
        if any(scope.organization_id != organization_id for scope in scopes):
            raise MemoryError("Memory conflict scopes crossed organizations.")

        source = aliased(MemoryModel)
        target = aliased(MemoryModel)
        relationships = MemoryRelationshipModel
        rows = await self._session.execute(
            select(relationships, source, target)
            .join(
                source,
                (source.id == relationships.source_memory_id)
                & (source.organization_id == relationships.organization_id),
            )
            .join(
                target,
                (target.id == relationships.target_memory_id)
                & (target.organization_id == relationships.organization_id),
            )
            .where(
                relationships.organization_id == organization_id,
                relationships.kind == MemoryRelationshipKind.CONFLICTS_WITH,
                relationships.deleted.is_(False),
                tuple_(relationships.scope_level, relationships.owner_id).in_(
                    [(scope.level, scope.owner_id) for scope in scopes]
                ),
                or_(
                    relationships.source_memory_id.in_(selected_ids),
                    relationships.target_memory_id.in_(selected_ids),
                ),
                source.state_revision == relationships.source_state_revision,
                target.state_revision == relationships.target_state_revision,
                source.deleted.is_(False),
                target.deleted.is_(False),
                or_(source.expires_at.is_(None), source.expires_at > func.now()),
                or_(target.expires_at.is_(None), target.expires_at > func.now()),
            )
            .order_by(relationships.created_at.desc(), relationships.id.desc())
            .limit(max(1, min(limit, MAX_RECALLED_CONFLICTS)))
        )
        evidence: list[MemoryConflictEvidence] = []
        for relationship, source_fact, target_fact in rows:
            scope = MemoryScope(
                organization_id=organization_id,
                level=relationship.scope_level,
                owner_id=relationship.owner_id,
            )
            if (
                source_fact.scope_level is not scope.level
                or target_fact.scope_level is not scope.level
                or memory_owner_id(source_fact) != scope.owner_id
                or memory_owner_id(target_fact) != scope.owner_id
            ):
                raise MemoryError("Stored Memory conflict authority is invalid.")
            evidence.append(
                MemoryConflictEvidence(
                    relationship_id=relationship.id,
                    facts=(
                        _conflict_fact(source_fact, scope),
                        _conflict_fact(target_fact, scope),
                    ),
                    detected_at=relationship.created_at,
                )
            )
        return evidence


def _conflict_fact(fact: MemoryModel, scope: MemoryScope) -> MemoryConflictFact:
    return MemoryConflictFact(
        id=fact.id,
        content=fact.content,
        scope=scope,
        updated_at=fact.updated_at,
    )


__all__ = ["MAX_RECALLED_CONFLICTS", "MemoryConflictReader"]
