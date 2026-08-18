"""Organization-scoped Memory read models for operators."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select

from eylo.common.contracts.memory import MemoryLevel, MemoryProvenance
from eylo.common.contracts.memory_reconciliation import MemoryIntegrityState
from eylo.modules.agents.models import AgentsModel
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.memory.integrity import MemoryIntegrityProjector
from eylo.modules.memory.models import (
    MemoryChangeModel,
    MemoryModel,
    MemoryReconciliationEffectModel,
    MemoryReconciliationJobModel,
    MemoryRelationshipModel,
)
from eylo.modules.memory.schemas import (
    MemoryChangeRead,
    MemoryDetailRead,
    MemoryListRead,
    MemoryRead,
    MemoryReconciliationJobRead,
    MemoryRelationshipRead,
    MemoryRelationshipRole,
    MemorySort,
    MemoryStatus,
    SortDirection,
)
from eylo.modules.memory.service import memory_owner_id


class MemoryNotFound(Exception):
    """The organization cannot see the requested memory."""


class MemoryOperatorService:
    def __init__(self, session) -> None:
        self._session = session

    async def list(
        self,
        *,
        organization_id: UUID,
        levels: list[MemoryLevel],
        statuses: list[MemoryStatus],
        integrities: list[MemoryIntegrityState],
        recalled: bool | None,
        query: str | None,
        sort: MemorySort,
        direction: SortDirection,
        limit: int,
        offset: int,
    ) -> MemoryListRead:
        filters = self._filters(
            organization_id=organization_id,
            levels=levels,
            statuses=statuses,
            integrities=integrities,
            recalled=recalled,
            query=query,
        )
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(MemoryModel).where(*filters)
            )
            or 0
        )
        order_column = {
            MemorySort.UPDATED_AT: MemoryModel.updated_at,
            MemorySort.CREATED_AT: MemoryModel.created_at,
            MemorySort.LAST_RECALLED_AT: MemoryModel.last_recalled_at,
            MemorySort.EXPIRES_AT: MemoryModel.expires_at,
            MemorySort.RECALL_COUNT: MemoryModel.recall_count,
        }[sort]
        order = (
            order_column.asc().nulls_last()
            if direction is SortDirection.ASC
            else order_column.desc().nulls_last()
        )
        models = list(
            await self._session.scalars(
                select(MemoryModel)
                .where(*filters)
                .order_by(order, MemoryModel.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        labels = await self._subject_labels(models, organization_id)
        integrity = await MemoryIntegrityProjector(self._session).for_models(models)
        return MemoryListRead(
            items=[self._read(model, labels, integrity) for model in models],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get(
        self,
        *,
        organization_id: UUID,
        memory_id: UUID,
    ) -> MemoryDetailRead:
        model = await self._session.scalar(
            select(MemoryModel).where(
                MemoryModel.id == memory_id,
                MemoryModel.organization_id == organization_id,
                MemoryModel.deleted.is_(False),
            )
        )
        if model is None:
            raise MemoryNotFound
        changes = list(
            await self._session.scalars(
                select(MemoryChangeModel)
                .where(
                    MemoryChangeModel.memory_id == memory_id,
                    MemoryChangeModel.organization_id == organization_id,
                    MemoryChangeModel.deleted.is_(False),
                )
                .order_by(MemoryChangeModel.created_at.asc())
            )
        )
        relationship_models = list(
            await self._session.scalars(
                select(MemoryRelationshipModel)
                .where(
                    MemoryRelationshipModel.organization_id == organization_id,
                    MemoryRelationshipModel.deleted.is_(False),
                    or_(
                        MemoryRelationshipModel.source_memory_id == memory_id,
                        MemoryRelationshipModel.target_memory_id == memory_id,
                    ),
                )
                .order_by(
                    MemoryRelationshipModel.created_at.desc(),
                    MemoryRelationshipModel.id.desc(),
                )
            )
        )
        related_ids = {
            (
                relationship.target_memory_id
                if relationship.source_memory_id == memory_id
                else relationship.source_memory_id
            )
            for relationship in relationship_models
        }
        related_models = (
            []
            if not related_ids
            else list(
                await self._session.scalars(
                    select(MemoryModel).where(
                        MemoryModel.organization_id == organization_id,
                        MemoryModel.id.in_(related_ids),
                        MemoryModel.deleted.is_(False),
                    )
                )
            )
        )
        visible_models = [model, *related_models]
        labels = await self._subject_labels(visible_models, organization_id)
        integrity = await MemoryIntegrityProjector(self._session).for_models(
            visible_models
        )
        summary = self._read(model, labels, integrity)
        by_id = {item.id: item for item in visible_models}
        relationships = [
            self._relationship_read(
                memory_id=memory_id,
                relationship=relationship,
                by_id=by_id,
                labels=labels,
                integrity=integrity,
            )
            for relationship in relationship_models
            if (
                relationship.source_memory_id in by_id
                and relationship.target_memory_id in by_id
            )
        ]
        latest_reconciliation = await self._latest_reconciliation(
            organization_id=organization_id,
            memory_id=memory_id,
            changes=changes,
            relationships=relationship_models,
        )
        return MemoryDetailRead(
            **summary.model_dump(),
            metadata=model.meta or {},
            provenance=MemoryProvenance.model_validate(model.provenance),
            history=[
                MemoryChangeRead(
                    id=change.id,
                    event=change.event,
                    before=change.before,
                    after=change.after,
                    created_at=change.created_at,
                    source_conversation_id=change.source_conversation_id,
                    provenance=MemoryProvenance.model_validate(change.provenance),
                )
                for change in changes
            ],
            relationships=relationships,
            latest_reconciliation=latest_reconciliation,
        )

    def _relationship_read(
        self,
        *,
        memory_id: UUID,
        relationship: MemoryRelationshipModel,
        by_id: dict[UUID, MemoryModel],
        labels: dict[tuple[MemoryLevel, UUID], str],
        integrity: dict[UUID, MemoryIntegrityState],
    ) -> MemoryRelationshipRead:
        source = by_id[relationship.source_memory_id]
        target = by_id[relationship.target_memory_id]
        is_source = relationship.source_memory_id == memory_id
        related = target if is_source else source
        return MemoryRelationshipRead(
            id=relationship.id,
            kind=relationship.kind,
            memory_role=(
                MemoryRelationshipRole.SOURCE
                if is_source
                else MemoryRelationshipRole.TARGET
            ),
            current=(
                relationship.source_state_revision == source.state_revision
                and relationship.target_state_revision == target.state_revision
            ),
            related_memory=self._read(related, labels, integrity),
            reconciliation_job_id=relationship.reconciliation_job_id,
            created_at=relationship.created_at,
        )

    async def _latest_reconciliation(
        self,
        *,
        organization_id: UUID,
        memory_id: UUID,
        changes: list[MemoryChangeModel],
        relationships: list[MemoryRelationshipModel],
    ) -> MemoryReconciliationJobRead | None:
        job_ids = {
            change.reconciliation_job_id
            for change in changes
            if change.reconciliation_job_id is not None
        }
        job_ids.update(
            relationship.reconciliation_job_id for relationship in relationships
        )
        input_job_ids = await self._session.scalars(
            select(MemoryReconciliationEffectModel.reconciliation_job_id).where(
                MemoryReconciliationEffectModel.organization_id == organization_id,
                MemoryReconciliationEffectModel.deleted.is_(False),
                or_(
                    MemoryReconciliationEffectModel.inputs["inputs"].contains(
                        [{"memory_id": str(memory_id)}]
                    ),
                    MemoryReconciliationEffectModel.inputs["settlements"].contains(
                        [{"memory_id": str(memory_id)}]
                    ),
                ),
            )
        )
        job_ids.update(input_job_ids.all())
        if not job_ids:
            return None
        job = await self._session.scalar(
            select(MemoryReconciliationJobModel)
            .where(
                MemoryReconciliationJobModel.organization_id == organization_id,
                MemoryReconciliationJobModel.id.in_(job_ids),
                MemoryReconciliationJobModel.deleted.is_(False),
            )
            .order_by(
                MemoryReconciliationJobModel.created_at.desc(),
                MemoryReconciliationJobModel.id.desc(),
            )
            .limit(1)
        )
        return None if job is None else self._job_read(job)

    @staticmethod
    def _job_read(job: MemoryReconciliationJobModel) -> MemoryReconciliationJobRead:
        return MemoryReconciliationJobRead(
            id=job.id,
            state=job.state,
            generation=job.generation,
            change_count=job.change_count,
            considered_count=job.considered_count,
            duplicate_count=job.duplicate_count,
            superseded_count=job.superseded_count,
            conflict_count=job.conflict_count,
            unrelated_count=job.unrelated_count,
            failed_count=job.failed_count,
            attempts=job.attempts,
            started_at=job.started_at,
            finished_at=job.finished_at,
            last_error=job.last_error,
            created_at=job.created_at,
        )

    @staticmethod
    def _filters(
        *,
        organization_id: UUID,
        levels: list[MemoryLevel],
        statuses: list[MemoryStatus],
        integrities: list[MemoryIntegrityState],
        recalled: bool | None,
        query: str | None,
    ) -> list:
        filters = [
            MemoryModel.organization_id == organization_id,
            MemoryModel.deleted.is_(False),
        ]
        if levels:
            filters.append(MemoryModel.scope_level.in_(levels))
        if integrities:
            filters.append(
                MemoryIntegrityProjector.filter_expression(integrities)
            )
        status_set = set(statuses)
        if status_set == {MemoryStatus.EXPIRED}:
            filters.append(
                and_(
                    MemoryModel.expires_at.is_not(None),
                    MemoryModel.expires_at <= func.now(),
                )
            )
        elif status_set == {MemoryStatus.ACTIVE}:
            filters.append(
                or_(
                    MemoryModel.expires_at.is_(None),
                    MemoryModel.expires_at > func.now(),
                )
            )
        if recalled is True:
            filters.append(MemoryModel.recall_count > 0)
        elif recalled is False:
            filters.append(MemoryModel.recall_count == 0)
        if query:
            escaped = _escape_like(query.strip())
            if escaped:
                filters.append(
                    MemoryModel.content.ilike(f"%{escaped}%", escape="\\")
                )
        return filters

    async def _subject_labels(
        self,
        models: list[MemoryModel],
        organization_id: UUID,
    ) -> dict[tuple[MemoryLevel, UUID], str]:
        labels: dict[tuple[MemoryLevel, UUID], str] = {}
        agent_ids = {model.agent_id for model in models if model.agent_id is not None}
        contact_ids = {
            model.contact_id for model in models if model.contact_id is not None
        }
        conversation_ids = {
            model.conversation_id
            for model in models
            if model.conversation_id is not None
        }
        if agent_ids:
            rows = await self._session.execute(
                select(AgentsModel.id, AgentsModel.name).where(
                    AgentsModel.organization_id == organization_id,
                    AgentsModel.id.in_(agent_ids),
                )
            )
            labels.update(
                {
                    (MemoryLevel.AGENT, row.id): row.name
                    or f"Agent {str(row.id)[:8]}"
                    for row in rows
                }
            )
        if contact_ids:
            rows = await self._session.execute(
                select(
                    ContactsModel.id,
                    ContactsModel.name,
                    ContactsModel.primary_email,
                    ContactsModel.primary_phone,
                ).where(
                    ContactsModel.organization_id == organization_id,
                    ContactsModel.id.in_(contact_ids),
                )
            )
            labels.update(
                {
                    (MemoryLevel.USER, row.id): row.name
                    or row.primary_email
                    or row.primary_phone
                    or f"User {str(row.id)[:8]}"
                    for row in rows
                }
            )
        if conversation_ids:
            rows = await self._session.execute(
                select(
                    ConversationsModel.id,
                    ConversationsModel.external_id,
                ).where(
                    ConversationsModel.organization_id == organization_id,
                    ConversationsModel.id.in_(conversation_ids),
                )
            )
            labels.update(
                {
                    (MemoryLevel.CONVERSATION, row.id): row.external_id
                    or f"Conversation {str(row.id)[:8]}"
                    for row in rows
                }
            )
        return labels

    @staticmethod
    def _read(
        model: MemoryModel,
        labels: dict[tuple[MemoryLevel, UUID], str],
        integrity: dict[UUID, MemoryIntegrityState],
    ) -> MemoryRead:
        owner_id = memory_owner_id(model)
        level = model.scope_level
        now = datetime.now(timezone.utc)
        status = (
            MemoryStatus.EXPIRED
            if model.expires_at is not None and model.expires_at <= now
            else MemoryStatus.ACTIVE
        )
        return MemoryRead(
            id=model.id,
            content=model.content,
            level=level,
            subject_id=owner_id,
            subject_label=labels.get(
                (level, owner_id),
                f"{level.value.title()} {str(owner_id)[:8]}",
            ),
            status=status,
            integrity=integrity[model.id],
            source_conversation_id=model.source_conversation_id,
            recall_count=model.recall_count,
            last_recalled_at=model.last_recalled_at,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = ["MemoryNotFound", "MemoryOperatorService"]
