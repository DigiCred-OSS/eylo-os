"""Application services for the `agents` domain."""

from __future__ import annotations

from typing import Optional, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.services import EyloBaseService
from eylo.modules.agents.kinds import assert_attachment_is_valid
from eylo.modules.agents.repositories import AgentBackgroundAgentRepository
from eylo.modules.agents.schemas.indb import AgentBackgroundAgentInDb


class AgentBackgroundAgentService(EyloBaseService[AgentBackgroundAgentInDb]):
    @property
    def schema(self) -> Type[AgentBackgroundAgentInDb]:
        return AgentBackgroundAgentInDb

    @property
    def repository(self) -> AgentBackgroundAgentRepository:
        return self._repository

    @repository.setter
    def repository(self, repo: AgentBackgroundAgentRepository):
        self._repository = repo

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = AgentBackgroundAgentRepository(db)

    async def attach(
        self,
        *,
        agent_id: UUID,
        background_agent_id: UUID,
        organization_id: UUID,
        expected_draft_version: int,
    ) -> AgentBackgroundAgentInDb:
        """Attach a background agent, disabled.

        Created disabled deliberately: wiring an attachment up and switching it
        on are different decisions, and the second one should be explicit.
        """
        await self._assert_valid(
            agent_id=agent_id,
            background_agent_id=background_agent_id,
            organization_id=organization_id,
        )
        mapping = await self.repository.create_(
            agent_id=agent_id,
            background_agent_id=background_agent_id,
            enabled=False,
        )
        await self._mark_draft_changed(
            organization_id,
            agent_id,
            expected_draft_version,
        )
        return self.orm_to_schema(mapping)

    async def set_enabled(
        self,
        *,
        agent_id: UUID,
        background_agent_id: UUID,
        organization_id: UUID,
        enabled: bool,
        expected_draft_version: int,
    ) -> Optional[AgentBackgroundAgentInDb]:
        """Turn an existing attachment on or off.

        Re-validated rather than trusted: the attachment was checked when it
        was created, but either agent may have been edited since, and enabling
        is the moment the configuration starts actually dispatching.
        """
        await self._get_agent(agent_id, organization_id)
        mapping = await self.repository.get_attachment(agent_id, background_agent_id)
        if mapping is None:
            return None

        if mapping.enabled is enabled:
            return self.orm_to_schema(mapping)

        if enabled:
            await self._assert_valid(
                agent_id=agent_id,
                background_agent_id=background_agent_id,
                organization_id=organization_id,
            )

        mapping.enabled = enabled
        saved = await self.repository.save_(mapping)
        await self._mark_draft_changed(
            organization_id,
            agent_id,
            expected_draft_version,
        )
        return self.orm_to_schema(saved)

    async def list_for_agent(
        self, agent_id: UUID, organization_id: UUID
    ) -> list[AgentBackgroundAgentInDb]:
        await self._get_agent(agent_id, organization_id)
        return self.orm_to_schema_list(
            await self.repository.list_by_agent_id(agent_id)
        )

    async def list_enabled_for_agent(
        self, agent_id: UUID
    ) -> list[AgentBackgroundAgentInDb]:
        """What dispatch reads. No organization check — see the note below.

        The caller is the dispatch hook, which already holds an agent it
        resolved through an org-scoped path, and both sides of every attachment
        are agents in that same organization by construction.
        """
        return self.orm_to_schema_list(
            await self.repository.list_enabled_by_agent_id(agent_id)
        )

    async def detach(
        self,
        *,
        agent_id: UUID,
        background_agent_id: UUID,
        organization_id: UUID,
        expected_draft_version: int,
    ) -> bool:
        await self._get_agent(agent_id, organization_id)
        removed = await self.repository.delete_attachment(
            agent_id,
            background_agent_id,
        )
        if removed:
            await self._mark_draft_changed(
                organization_id,
                agent_id,
                expected_draft_version,
            )
        return removed

    async def _mark_draft_changed(
        self,
        organization_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
    ) -> None:
        from eylo.modules.agents.services.revisions import AgentRevisionService

        await AgentRevisionService(
            self.repository.db_session
        ).mark_draft_changed(
            organization_id=organization_id,
            agent_id=agent_id,
            expected_draft_version=expected_draft_version,
        )

    async def _get_agent(self, agent_id: UUID, organization_id: UUID):
        from eylo.modules.agents.services.indb import AgentService

        return await AgentService().get_by_organization_and_id(
            organization_id=organization_id, pk=agent_id
        )

    async def _assert_valid(
        self, *, agent_id: UUID, background_agent_id: UUID, organization_id: UUID
    ) -> None:
        """Fetch both agents through the same organization-scoped authority."""
        from eylo.modules.agents.services.indb import AgentService

        owner = await self._get_agent(agent_id, organization_id)
        target = await AgentService().get_by_organization_and_id(
            organization_id=organization_id,
            pk=background_agent_id,
        )

        assert_attachment_is_valid(
            owner_kind=owner.kind,
            owner_id=agent_id,
            owner_organization_id=owner.organization_id,
            target_kind=target.kind,
            target_id=background_agent_id,
            target_organization_id=target.organization_id,
        )
