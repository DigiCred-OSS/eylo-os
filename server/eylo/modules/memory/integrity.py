"""Derive current Memory integrity independently from lifecycle status."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from eylo.common.contracts.memory_reconciliation import (
    MemoryIntegrityState,
    MemoryRelationshipKind,
)
from eylo.modules.memory.models import MemoryModel, MemoryRelationshipModel

_PRECEDENCE = {
    MemoryIntegrityState.HEALTHY: 0,
    MemoryIntegrityState.CONSOLIDATED: 1,
    MemoryIntegrityState.CONFLICTED: 2,
    MemoryIntegrityState.CHECKING: 3,
}


class MemoryIntegrityProjector:
    """Project revision-fenced relationships onto current fact revisions."""

    def __init__(self, session) -> None:
        self._session = session

    @staticmethod
    def filter_expression(states: list[MemoryIntegrityState]):
        """Return SQL equivalent to the backend integrity precedence."""
        requested = set(states)
        peer = aliased(MemoryModel)
        source_conflict = exists(
            select(MemoryRelationshipModel.id)
            .join(
                peer,
                (peer.id == MemoryRelationshipModel.target_memory_id)
                & (
                    peer.organization_id
                    == MemoryRelationshipModel.organization_id
                ),
            )
            .where(
                MemoryRelationshipModel.organization_id
                == MemoryModel.organization_id,
                MemoryRelationshipModel.source_memory_id == MemoryModel.id,
                MemoryRelationshipModel.kind
                == MemoryRelationshipKind.CONFLICTS_WITH,
                MemoryRelationshipModel.source_state_revision
                == MemoryModel.state_revision,
                MemoryRelationshipModel.target_state_revision
                == peer.state_revision,
                MemoryRelationshipModel.deleted.is_(False),
            )
            .correlate(MemoryModel)
        )
        target_conflict = exists(
            select(MemoryRelationshipModel.id)
            .join(
                peer,
                (peer.id == MemoryRelationshipModel.source_memory_id)
                & (
                    peer.organization_id
                    == MemoryRelationshipModel.organization_id
                ),
            )
            .where(
                MemoryRelationshipModel.organization_id
                == MemoryModel.organization_id,
                MemoryRelationshipModel.target_memory_id == MemoryModel.id,
                MemoryRelationshipModel.kind
                == MemoryRelationshipKind.CONFLICTS_WITH,
                MemoryRelationshipModel.target_state_revision
                == MemoryModel.state_revision,
                MemoryRelationshipModel.source_state_revision
                == peer.state_revision,
                MemoryRelationshipModel.deleted.is_(False),
            )
            .correlate(MemoryModel)
        )
        conflicted = or_(source_conflict, target_conflict)
        consolidated = exists(
            select(MemoryRelationshipModel.id)
            .where(
                MemoryRelationshipModel.organization_id
                == MemoryModel.organization_id,
                MemoryRelationshipModel.source_memory_id == MemoryModel.id,
                MemoryRelationshipModel.kind.in_(
                    (
                        MemoryRelationshipKind.DUPLICATE_OF,
                        MemoryRelationshipKind.SUPERSEDED_BY,
                    )
                ),
                MemoryRelationshipModel.source_state_revision
                == MemoryModel.state_revision,
                MemoryRelationshipModel.deleted.is_(False),
            )
            .correlate(MemoryModel)
        )
        checking = MemoryModel.reconciled_state_revision < MemoryModel.state_revision
        expressions = {
            MemoryIntegrityState.CHECKING: checking,
            MemoryIntegrityState.CONFLICTED: and_(~checking, conflicted),
            MemoryIntegrityState.CONSOLIDATED: and_(
                ~checking,
                ~conflicted,
                consolidated,
            ),
            MemoryIntegrityState.HEALTHY: and_(
                ~checking,
                ~conflicted,
                ~consolidated,
            ),
        }
        return or_(*(expressions[state] for state in requested))

    async def for_models(
        self,
        models: list[MemoryModel],
    ) -> dict[UUID, MemoryIntegrityState]:
        states = {
            model.id: (
                MemoryIntegrityState.CHECKING
                if model.reconciled_state_revision < model.state_revision
                else MemoryIntegrityState.HEALTHY
            )
            for model in models
        }
        if not states:
            return states

        source = aliased(MemoryModel)
        target = aliased(MemoryModel)
        rows = await self._session.execute(
            select(
                MemoryRelationshipModel,
                source.state_revision.label("current_source_revision"),
                target.state_revision.label("current_target_revision"),
            )
            .join(
                source,
                (source.id == MemoryRelationshipModel.source_memory_id)
                & (
                    source.organization_id
                    == MemoryRelationshipModel.organization_id
                ),
            )
            .join(
                target,
                (target.id == MemoryRelationshipModel.target_memory_id)
                & (
                    target.organization_id
                    == MemoryRelationshipModel.organization_id
                ),
            )
            .where(
                MemoryRelationshipModel.organization_id
                == models[0].organization_id,
                MemoryRelationshipModel.deleted.is_(False),
                or_(
                    MemoryRelationshipModel.source_memory_id.in_(states),
                    MemoryRelationshipModel.target_memory_id.in_(states),
                ),
            )
        )
        for row in rows:
            relationship = row[0]
            kind = MemoryRelationshipKind(relationship.kind)
            source_is_current = (
                relationship.source_state_revision
                == row.current_source_revision
            )
            target_is_current = (
                relationship.target_state_revision
                == row.current_target_revision
            )
            if (
                kind is MemoryRelationshipKind.CONFLICTS_WITH
                and source_is_current
                and target_is_current
            ):
                _promote(
                    states,
                    relationship.source_memory_id,
                    MemoryIntegrityState.CONFLICTED,
                )
                _promote(
                    states,
                    relationship.target_memory_id,
                    MemoryIntegrityState.CONFLICTED,
                )
            elif (
                kind
                in {
                    MemoryRelationshipKind.DUPLICATE_OF,
                    MemoryRelationshipKind.SUPERSEDED_BY,
                }
                and source_is_current
            ):
                _promote(
                    states,
                    relationship.source_memory_id,
                    MemoryIntegrityState.CONSOLIDATED,
                )
        return states


def _promote(
    states: dict[UUID, MemoryIntegrityState],
    memory_id: UUID,
    candidate: MemoryIntegrityState,
) -> None:
    current = states.get(memory_id)
    if current is not None and _PRECEDENCE[candidate] > _PRECEDENCE[current]:
        states[memory_id] = candidate


__all__ = ["MemoryIntegrityProjector"]
