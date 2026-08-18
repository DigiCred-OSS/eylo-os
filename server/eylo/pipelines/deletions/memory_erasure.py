"""Exact typed-owner erasure for Memory facts and durable support state."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.memory import MemoryLevel, MemoryScope
from eylo.modules.agent_runs.models import OrganizationExecutionReservationModel
from eylo.modules.memory.models import (
    MemoryChangeModel,
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationEffectModel,
    MemoryReconciliationJobModel,
    MemoryReindexVectorModel,
    MemoryRelationshipModel,
)


class MemoryOwnerGraphChanged(Exception):
    """A reconciliation generation appeared while its owner was being erased."""


@dataclass(frozen=True, slots=True)
class MemoryOwnerErasure:
    """IDs erased for one exact Memory owner partition."""

    fact_ids: frozenset[UUID]
    reconciliation_job_ids: frozenset[UUID]


async def erase_memory_owner(
    session: AsyncSession,
    scope: MemoryScope,
) -> MemoryOwnerErasure:
    """Erase facts, history, and derived work owned by one typed subject.

    Reindex jobs are configuration-owned and may include other subjects. Only
    this owner's staged vectors are removed; the active reindex catches up from
    the remaining fact set before cutover.
    """
    partition = _partition_predicates(scope)
    owner = _owner_predicates(scope)

    initial_job_ids = frozenset(
        (
            await session.scalars(
                select(MemoryReconciliationJobModel.id)
                .where(*partition(MemoryReconciliationJobModel))
                .order_by(MemoryReconciliationJobModel.id)
                .with_for_update()
            )
        ).all()
    )
    await session.scalars(
        select(MemoryReconciliationCursorModel.id)
        .where(*partition(MemoryReconciliationCursorModel))
        .order_by(MemoryReconciliationCursorModel.id)
        .with_for_update()
    )
    stable_job_ids = frozenset(
        (
            await session.scalars(
                select(MemoryReconciliationJobModel.id).where(
                    *partition(MemoryReconciliationJobModel)
                )
            )
        ).all()
    )
    if stable_job_ids != initial_job_ids:
        raise MemoryOwnerGraphChanged

    fact_ids = frozenset(
        (
            await session.scalars(
                select(MemoryModel.id)
                .where(*owner(MemoryModel))
                .order_by(MemoryModel.id)
                .with_for_update()
            )
        ).all()
    )

    await session.execute(
        delete(MemoryReconciliationCursorModel).where(
            *partition(MemoryReconciliationCursorModel)
        )
    )
    await session.execute(
        delete(MemoryRelationshipModel).where(*partition(MemoryRelationshipModel))
    )
    if stable_job_ids:
        await session.execute(
            delete(OrganizationExecutionReservationModel).where(
                OrganizationExecutionReservationModel.organization_id
                == scope.organization_id,
                OrganizationExecutionReservationModel.memory_reconciliation_job_id.in_(
                    stable_job_ids
                ),
            )
        )
        await session.execute(
            delete(MemoryReconciliationEffectModel).where(
                MemoryReconciliationEffectModel.organization_id
                == scope.organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id.in_(
                    stable_job_ids
                ),
            )
        )
    await session.execute(
        delete(MemoryReconciliationJobModel).where(
            *partition(MemoryReconciliationJobModel)
        )
    )
    await session.execute(delete(MemoryChangeModel).where(*owner(MemoryChangeModel)))
    if fact_ids:
        await session.execute(
            delete(MemoryReindexVectorModel).where(
                MemoryReindexVectorModel.organization_id == scope.organization_id,
                MemoryReindexVectorModel.memory_id.in_(fact_ids),
            )
        )
    await session.execute(delete(MemoryModel).where(*owner(MemoryModel)))
    await session.flush()
    await _require_owner_absent(
        session,
        scope=scope,
        fact_ids=fact_ids,
        reconciliation_job_ids=stable_job_ids,
    )
    return MemoryOwnerErasure(
        fact_ids=fact_ids,
        reconciliation_job_ids=stable_job_ids,
    )


def _partition_predicates(scope: MemoryScope):
    def predicates(model) -> tuple:
        return (
            model.organization_id == scope.organization_id,
            model.scope_level == scope.level,
            model.owner_id == scope.owner_id,
        )

    return predicates


def _owner_predicates(scope: MemoryScope):
    owner_field = {
        MemoryLevel.AGENT: "agent_id",
        MemoryLevel.USER: "contact_id",
        MemoryLevel.CONVERSATION: "conversation_id",
    }[scope.level]

    def predicates(model) -> tuple:
        return (
            model.organization_id == scope.organization_id,
            model.scope_level == scope.level,
            getattr(model, owner_field) == scope.owner_id,
        )

    return predicates


async def _require_owner_absent(
    session: AsyncSession,
    *,
    scope: MemoryScope,
    fact_ids: frozenset[UUID],
    reconciliation_job_ids: frozenset[UUID],
) -> None:
    partition = _partition_predicates(scope)
    owner = _owner_predicates(scope)
    checks = (
        select(MemoryModel.id).where(*owner(MemoryModel)),
        select(MemoryChangeModel.id).where(*owner(MemoryChangeModel)),
        select(MemoryReconciliationCursorModel.id).where(
            *partition(MemoryReconciliationCursorModel)
        ),
        select(MemoryReconciliationJobModel.id).where(
            *partition(MemoryReconciliationJobModel)
        ),
        select(MemoryRelationshipModel.id).where(*partition(MemoryRelationshipModel)),
    )
    for check in checks:
        if await session.scalar(check) is not None:
            raise RuntimeError("Memory erasure left a typed-owner row.")
    if fact_ids:
        remaining_vector = await session.scalar(
            select(MemoryReindexVectorModel.id).where(
                MemoryReindexVectorModel.organization_id == scope.organization_id,
                MemoryReindexVectorModel.memory_id.in_(fact_ids),
            )
        )
        if remaining_vector is not None:
            raise RuntimeError("Memory erasure left a staged owner vector.")
    if reconciliation_job_ids:
        remaining_effect = await session.scalar(
            select(MemoryReconciliationEffectModel.id).where(
                MemoryReconciliationEffectModel.organization_id
                == scope.organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id.in_(
                    reconciliation_job_ids
                ),
            )
        )
        if remaining_effect is not None:
            raise RuntimeError("Memory erasure left a reconciliation effect.")
        remaining_reservation = await session.scalar(
            select(OrganizationExecutionReservationModel.id).where(
                OrganizationExecutionReservationModel.organization_id
                == scope.organization_id,
                OrganizationExecutionReservationModel.memory_reconciliation_job_id.in_(
                    reconciliation_job_ids
                ),
            )
        )
        if remaining_reservation is not None:
            raise RuntimeError("Memory erasure left an execution reservation.")


__all__ = [
    "MemoryOwnerErasure",
    "MemoryOwnerGraphChanged",
    "erase_memory_owner",
]
