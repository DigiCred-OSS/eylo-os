"""Organization-scoped persistence for durable agent-run projections."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agent_runs.domain import AgentRunLifecycle, AgentRunOriginKind
from eylo.modules.agent_runs.models import (
    AgentInputRequestModel,
    AgentRunModel,
    AgentRunStepModel,
    OrganizationExecutionReservationModel,
)


class AgentRunRepository:
    """Require organization scope on every run and child lookup."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def acquire_filing_lock(self, idempotency_key: str) -> None:
        """Serialize one PostgreSQL transaction per stable run filing."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:idempotency_key, 0))"),
            {"idempotency_key": idempotency_key},
        )

    async def get_by_idempotency_key(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
    ) -> AgentRunModel | None:
        query = select(AgentRunModel).where(
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.idempotency_key == idempotency_key,
            AgentRunModel.deleted.is_(False),
        )
        return (await self._session.execute(query)).scalar_one_or_none()

    async def get(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        for_update: bool = False,
    ) -> AgentRunModel | None:
        query = select(AgentRunModel).where(
            AgentRunModel.id == run_id,
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return (await self._session.execute(query)).scalar_one_or_none()

    async def get_by_origin_message(
        self,
        *,
        organization_id: UUID,
        message_id: UUID,
    ) -> AgentRunModel | None:
        """Resolve the one durable run filed for a message origin."""
        query = select(AgentRunModel).where(
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.origin_message_id == message_id,
            AgentRunModel.deleted.is_(False),
        )
        return (await self._session.execute(query)).scalar_one_or_none()

    async def get_by_origin_schedule_run(
        self,
        *,
        organization_id: UUID,
        schedule_run_id: UUID,
    ) -> AgentRunModel | None:
        """Resolve the one durable run filed for a schedule occurrence."""
        query = select(AgentRunModel).where(
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.origin_schedule_run_id == schedule_run_id,
            AgentRunModel.deleted.is_(False),
        )
        return (await self._session.execute(query)).scalar_one_or_none()

    async def list(
        self,
        *,
        organization_id: UUID,
        limit: int,
        offset: int,
        origin_kind: AgentRunOriginKind | None = None,
        agent_id: UUID | None = None,
        lifecycle: AgentRunLifecycle | None = None,
    ) -> Sequence[AgentRunModel]:
        query = select(AgentRunModel).where(
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.deleted.is_(False),
        )
        if origin_kind is not None:
            query = query.where(AgentRunModel.origin_kind == origin_kind)
        if agent_id is not None:
            query = query.where(AgentRunModel.agent_id == agent_id)
        if lifecycle is not None:
            query = query.where(AgentRunModel.lifecycle == lifecycle)
        query = (
            query.order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self._session.execute(query)).scalars().all()

    async def list_steps(
        self,
        *,
        organization_id: UUID,
        run_ids: Sequence[UUID],
    ) -> Sequence[AgentRunStepModel]:
        if not run_ids:
            return []
        query = self._child_query(AgentRunStepModel, organization_id, run_ids).order_by(
            AgentRunStepModel.created_at.asc(), AgentRunStepModel.id.asc()
        )
        return (await self._session.execute(query)).scalars().all()

    async def list_input_requests(
        self,
        *,
        organization_id: UUID,
        run_ids: Sequence[UUID],
    ) -> Sequence[AgentInputRequestModel]:
        if not run_ids:
            return []
        query = self._child_query(
            AgentInputRequestModel,
            organization_id,
            run_ids,
        ).order_by(
            AgentInputRequestModel.created_at.asc(),
            AgentInputRequestModel.id.asc(),
        )
        return (await self._session.execute(query)).scalars().all()

    async def list_reservations(
        self,
        *,
        organization_id: UUID,
        run_ids: Sequence[UUID],
    ) -> Sequence[OrganizationExecutionReservationModel]:
        if not run_ids:
            return []
        query = self._child_query(
            OrganizationExecutionReservationModel,
            organization_id,
            run_ids,
        )
        return (await self._session.execute(query)).scalars().all()

    async def get_input_request(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        request_id: UUID,
        for_update: bool = False,
    ) -> AgentInputRequestModel | None:
        query = (
            select(AgentInputRequestModel)
            .join(
                AgentRunModel,
                and_(
                    AgentRunModel.id == AgentInputRequestModel.run_id,
                    AgentRunModel.organization_id
                    == AgentInputRequestModel.organization_id,
                ),
            )
            .where(
                AgentInputRequestModel.id == request_id,
                AgentInputRequestModel.run_id == run_id,
                AgentInputRequestModel.organization_id == organization_id,
                AgentInputRequestModel.deleted.is_(False),
                AgentRunModel.organization_id == organization_id,
                AgentRunModel.deleted.is_(False),
            )
        )
        if for_update:
            query = query.with_for_update(of=AgentInputRequestModel)
        return (await self._session.execute(query)).scalar_one_or_none()

    @staticmethod
    def _child_query(
        model: (
            type[AgentRunStepModel]
            | type[AgentInputRequestModel]
            | type[OrganizationExecutionReservationModel]
        ),
        organization_id: UUID,
        run_ids: Sequence[UUID],
    ) -> Select:
        return (
            select(model)
            .join(
                AgentRunModel,
                and_(
                    AgentRunModel.id == model.run_id,
                    AgentRunModel.organization_id == model.organization_id,
                ),
            )
            .where(
                model.run_id.in_(run_ids),
                model.organization_id == organization_id,
                model.deleted.is_(False),
                AgentRunModel.organization_id == organization_id,
                AgentRunModel.deleted.is_(False),
            )
        )
