"""Application services for mutable swarm drafts and immutable topologies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Type
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.revisions import (
    DefinitionHeaderState,
    DefinitionLifecycle,
    PublishedRevisionState,
)
from eylo.common.services import EyloBaseService
from eylo.modules.agents.domain import (
    InvalidSwarmDefinitionError,
    SwarmMemberNotFoundError,
    SwarmNotFoundError,
)
from eylo.modules.agents.models import (
    AgentKind,
    AgentRevisionModel,
    AgentSwarmMappingModel,
    AgentSwarmModel,
    AgentSwarmRevisionMemberModel,
    AgentSwarmRevisionModel,
    AgentsModel,
)
from eylo.modules.agents.repositories import (
    AgentSwarmMappingRepository,
    AgentSwarmRepository,
)
from eylo.modules.agents.schemas.swarm import AgentSwarmInDb, AgentSwarmMappingInDb

MAX_SWARM_DESCRIPTION_LENGTH = 2_000
MAX_SWARM_MEMBERS = 32


class AgentSwarmService(EyloBaseService[AgentSwarmInDb]):
    """Own stable swarm identity and mutable draft metadata."""

    @property
    def schema(self) -> Type[AgentSwarmInDb]:
        return AgentSwarmInDb

    @property
    def repository(self) -> AgentSwarmRepository:
        return self._repository

    @repository.setter
    def repository(self, repo: AgentSwarmRepository) -> None:
        self._repository = repo

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = AgentSwarmRepository(db)

    async def list_by_organization(self, organization_id: UUID) -> list[AgentSwarmInDb]:
        results = await self.repository.filter_all_(
            filters=[
                self.repository.model.organization_id == organization_id,
                self.repository.model.deleted.is_(False),
            ]
        )
        return self.orm_to_schema_list(results)

    async def get_by_id_and_organization(
        self,
        pk: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> AgentSwarmInDb | None:
        row = await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=pk,
            for_update=for_update,
            required=False,
        )
        return self.orm_to_schema(row) if row else None

    async def create(
        self,
        name: str,
        description: str | None,
        organization_id: UUID,
    ) -> AgentSwarmInDb:
        row = await self.repository.create(
            name=name,
            description=_description(description),
            organization_id=organization_id,
        )
        return self.orm_to_schema(row)

    async def update(
        self,
        *,
        pk: UUID,
        organization_id: UUID,
        expected_draft_version: int,
        name: str | None = None,
        description: str | None = None,
    ) -> AgentSwarmInDb:
        row = await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=pk,
            for_update=True,
        )
        next_state = _header_state(row).edit(
            expected_draft_version=expected_draft_version
        )
        if name is not None:
            row.name = name
        if description is not None:
            row.description = _description(description)
        _apply_header_state(row, next_state)
        await self.repository.db_session.flush()
        return self.orm_to_schema(row)

    async def delete_draft(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
    ) -> None:
        row = await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        if row.published_revision is not None:
            raise InvalidSwarmDefinitionError(
                "Published swarms must be withdrawn or revoked, not deleted."
            )
        row.deleted = True
        await self.repository.db_session.flush()


class AgentSwarmMappingService(EyloBaseService[AgentSwarmMappingInDb]):
    """Mutate draft membership while advancing the header draft version."""

    @property
    def schema(self) -> Type[AgentSwarmMappingInDb]:
        return AgentSwarmMappingInDb

    @property
    def repository(self) -> AgentSwarmMappingRepository:
        return self._repository

    @repository.setter
    def repository(self, repo: AgentSwarmMappingRepository) -> None:
        self._repository = repo

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = AgentSwarmMappingRepository(db)

    async def create(
        self,
        *,
        agent_id: UUID,
        swarm_id: UUID,
        organization_id: UUID,
        agent_description: str | None,
        expected_draft_version: int,
    ) -> AgentSwarmMappingInDb:
        header = await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        agent = await self.repository.db_session.scalar(
            select(AgentsModel).where(
                AgentsModel.id == agent_id,
                AgentsModel.organization_id == organization_id,
                AgentsModel.deleted.is_(False),
            )
        )
        if agent is None:
            raise SwarmMemberNotFoundError("Agent not found.")
        if _enum_value(agent.kind) != AgentKind.CONVERSATIONAL.value:
            raise InvalidSwarmDefinitionError(
                "Only conversational agents may join a swarm."
            )
        existing = await self.repository.db_session.scalar(
            select(AgentSwarmMappingModel).where(
                AgentSwarmMappingModel.organization_id == organization_id,
                AgentSwarmMappingModel.swarm_id == swarm_id,
                AgentSwarmMappingModel.agent_id == agent_id,
                AgentSwarmMappingModel.deleted.is_(False),
            )
        )
        if existing is not None:
            raise InvalidSwarmDefinitionError("Agent is already in this swarm draft.")

        next_state = _header_state(header).edit(
            expected_draft_version=expected_draft_version
        )
        row = await self.repository.create(
            agent_id=agent_id,
            swarm_id=swarm_id,
            organization_id=organization_id,
            agent_description=_description(agent_description),
        )
        _apply_header_state(header, next_state)
        await self.repository.db_session.flush()
        return self.orm_to_schema(row)

    async def list_by_swarm_id(
        self,
        swarm_id: UUID,
        organization_id: UUID,
    ) -> list[AgentSwarmMappingInDb]:
        await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=swarm_id,
        )
        results = await self.repository.list_by_swarm_id(swarm_id, organization_id)
        return self.orm_to_schema_list(results)

    async def list_by_agent_id(
        self,
        agent_id: UUID,
        organization_id: UUID,
    ) -> list[AgentSwarmMappingInDb]:
        mappings = await self.repository.db_session.scalars(
            select(AgentSwarmMappingModel).where(
                AgentSwarmMappingModel.agent_id == agent_id,
                AgentSwarmMappingModel.organization_id == organization_id,
                AgentSwarmMappingModel.deleted.is_(False),
            )
        )
        swarm_ids = [mapping.swarm_id for mapping in mappings.all()]
        if not swarm_ids:
            return []
        results = await self.repository.db_session.scalars(
            select(AgentSwarmMappingModel).where(
                AgentSwarmMappingModel.swarm_id.in_(swarm_ids),
                AgentSwarmMappingModel.organization_id == organization_id,
                AgentSwarmMappingModel.deleted.is_(False),
            )
        )
        return self.orm_to_schema_list(results.all())

    async def delete_agent_from_swarm(
        self,
        *,
        agent_id: UUID,
        swarm_id: UUID,
        organization_id: UUID,
        expected_draft_version: int,
    ) -> None:
        header = await _get_header(
            self.repository.db_session,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        mapping = await self.repository.db_session.scalar(
            select(AgentSwarmMappingModel).where(
                AgentSwarmMappingModel.agent_id == agent_id,
                AgentSwarmMappingModel.swarm_id == swarm_id,
                AgentSwarmMappingModel.organization_id == organization_id,
                AgentSwarmMappingModel.deleted.is_(False),
            )
        )
        if mapping is None:
            raise SwarmMemberNotFoundError("Agent is not in this swarm draft.")
        next_state = _header_state(header).edit(
            expected_draft_version=expected_draft_version
        )
        await self.repository.db_session.execute(
            delete(AgentSwarmMappingModel).where(
                AgentSwarmMappingModel.id == mapping.id
            )
        )
        _apply_header_state(header, next_state)
        await self.repository.db_session.flush()


class AgentSwarmRevisionService:
    """Publish and resolve immutable swarm topology revisions."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()

    async def publish(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        expected_draft_version: int,
        actor_id: UUID | None,
    ) -> AgentSwarmRevisionModel:
        header = await _get_header(
            self._db,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        next_revision = (header.published_revision or 0) + 1
        next_state = _header_state(header).publish(
            revision=next_revision,
            expected_draft_version=expected_draft_version,
        )
        draft_members = list(
            (
                await self._db.scalars(
                    select(AgentSwarmMappingModel)
                    .where(
                        AgentSwarmMappingModel.organization_id == organization_id,
                        AgentSwarmMappingModel.swarm_id == swarm_id,
                        AgentSwarmMappingModel.deleted.is_(False),
                    )
                    .order_by(AgentSwarmMappingModel.agent_id)
                )
            ).all()
        )
        if not draft_members:
            raise InvalidSwarmDefinitionError(
                "A swarm requires at least one conversational agent before publish."
            )
        if len(draft_members) > MAX_SWARM_MEMBERS:
            raise InvalidSwarmDefinitionError(
                f"A swarm cannot publish more than {MAX_SWARM_MEMBERS} members."
            )

        from eylo.modules.agents.services.revisions import AgentRevisionService

        exact_members: list[tuple[AgentSwarmMappingModel, AgentRevisionModel]] = []
        agent_revisions = AgentRevisionService(self._db)
        for member in draft_members:
            agent_revision = await agent_revisions.resolve_for_new_work(
                organization_id=organization_id,
                agent_id=member.agent_id,
                for_update=True,
            )
            if agent_revision.kind != AgentKind.CONVERSATIONAL.value:
                raise InvalidSwarmDefinitionError(
                    "Only published conversational agents may enter a topology."
                )
            exact_members.append((member, agent_revision))

        published_at = datetime.now(timezone.utc)
        revision = AgentSwarmRevisionModel(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=next_revision,
            name=header.name,
            slug=header.slug,
            description=header.description,
            published_at=published_at,
            published_by=actor_id,
        )
        self._db.add(revision)
        await self._db.flush()
        # SQLAlchemy's PostgreSQL insertmanyvalues sentinel cannot reconcile
        # uuid_utils.UUID defaults with stdlib UUID result values on this
        # driver. Swarms are bounded; individual INSERTs remain one atomic
        # transaction and avoid that driver-specific bulk path.
        for member, agent_revision in exact_members:
            self._db.add(
                AgentSwarmRevisionMemberModel(
                    organization_id=organization_id,
                    swarm_id=swarm_id,
                    swarm_revision=next_revision,
                    agent_id=member.agent_id,
                    agent_revision=agent_revision.revision,
                    agent_description=member.agent_description,
                )
            )
            await self._db.flush()
        _apply_header_state(header, next_state)
        await self._db.flush()
        return revision

    async def withdraw(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
    ) -> AgentSwarmModel:
        header = await _get_header(
            self._db,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        _apply_header_state(header, _header_state(header).withdraw())
        await self._db.flush()
        return header

    async def revoke(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> AgentSwarmRevisionModel:
        header = await _get_header(
            self._db,
            organization_id=organization_id,
            swarm_id=swarm_id,
            for_update=True,
        )
        row = await self.get_revision(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=revision,
            for_update=True,
        )
        revoked = _revision_state(row).revoke(
            actor_id=actor_id,
            reason=reason,
            at=datetime.now(timezone.utc),
        )
        row.availability = revoked.availability.value
        row.revoked_at = revoked.revoked_at
        row.revoked_by = revoked.revoked_by
        row.revocation_reason = revoked.revocation_reason
        row.cancellation_requested_at = revoked.cancellation_requested_at
        if header.published_revision == revision:
            _apply_header_state(header, _header_state(header).withdraw())
        await self._db.flush()
        return row

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
    ) -> AgentSwarmRevisionModel:
        header = await _get_header(
            self._db,
            organization_id=organization_id,
            swarm_id=swarm_id,
        )
        revision = _header_state(header).revision_for_new_work()
        return await self.get_revision(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=revision,
        )

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
        for_update: bool = False,
    ) -> AgentSwarmRevisionModel:
        query = select(AgentSwarmRevisionModel).where(
            AgentSwarmRevisionModel.organization_id == organization_id,
            AgentSwarmRevisionModel.swarm_id == swarm_id,
            AgentSwarmRevisionModel.revision == revision,
            AgentSwarmRevisionModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self._db.scalar(query)
        if row is None:
            raise SwarmNotFoundError("Swarm topology revision not found.")
        _revision_state(row).require_available()
        return row

    async def list_members(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
    ) -> list[AgentSwarmRevisionMemberModel]:
        rows = await self._db.scalars(
            select(AgentSwarmRevisionMemberModel)
            .where(
                AgentSwarmRevisionMemberModel.organization_id == organization_id,
                AgentSwarmRevisionMemberModel.swarm_id == swarm_id,
                AgentSwarmRevisionMemberModel.swarm_revision == revision,
                AgentSwarmRevisionMemberModel.deleted.is_(False),
            )
            .order_by(AgentSwarmRevisionMemberModel.agent_id)
        )
        return list(rows.all())


async def _get_header(
    db: AsyncSession,
    *,
    organization_id: UUID,
    swarm_id: UUID,
    for_update: bool = False,
    required: bool = True,
) -> AgentSwarmModel | None:
    query = select(AgentSwarmModel).where(
        AgentSwarmModel.organization_id == organization_id,
        AgentSwarmModel.id == swarm_id,
        AgentSwarmModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None and required:
        raise SwarmNotFoundError("Swarm not found.")
    return row


def _header_state(row: AgentSwarmModel) -> DefinitionHeaderState:
    return DefinitionHeaderState(
        lifecycle=DefinitionLifecycle(row.lifecycle),
        published_revision=row.published_revision,
        draft_version=row.draft_version,
        draft_dirty=row.draft_dirty,
    )


def _revision_state(row: AgentSwarmRevisionModel) -> PublishedRevisionState:
    return PublishedRevisionState(
        availability=row.availability,
        published_at=row.published_at,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
        cancellation_requested_at=row.cancellation_requested_at,
    )


def _apply_header_state(
    row: AgentSwarmModel,
    state: DefinitionHeaderState,
) -> None:
    row.lifecycle = state.lifecycle.value
    row.published_revision = state.published_revision
    row.draft_version = state.draft_version
    row.draft_dirty = state.draft_dirty


def _description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > MAX_SWARM_DESCRIPTION_LENGTH:
        raise InvalidSwarmDefinitionError(
            f"Swarm descriptions cannot exceed {MAX_SWARM_DESCRIPTION_LENGTH} characters."
        )
    return normalized


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


__all__ = [
    "AgentSwarmMappingService",
    "AgentSwarmRevisionService",
    "AgentSwarmService",
]
