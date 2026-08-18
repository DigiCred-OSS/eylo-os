"""Application orchestration around reusable Voice Config definitions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.revisions import DefinitionHeaderState, DefinitionLifecycle
from eylo.modules.agents.models import AgentsModel
from eylo.modules.voice.exceptions import VoiceConfigInUse
from eylo.modules.voice.schemas.api import (
    OrganizationVoiceConfigCreate,
    OrganizationVoiceConfigUpdate,
    VoiceConfigRead,
)
from eylo.modules.voice.services.voice_configs import VoiceConfigService


class VoiceConfigurationService:
    """Coordinate Voice Config changes with mutable Agent bindings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._voice_configs = VoiceConfigService(db)

    async def list(self, organization_id: UUID) -> list[VoiceConfigRead]:
        return await self._voice_configs.list(organization_id)

    async def get(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> VoiceConfigRead:
        return await self._voice_configs.get(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )

    async def create(
        self,
        *,
        organization_id: UUID,
        payload: OrganizationVoiceConfigCreate,
    ) -> VoiceConfigRead:
        return await self._voice_configs.create(
            organization_id=organization_id,
            payload=payload,
        )

    async def update(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        payload: OrganizationVoiceConfigUpdate,
    ) -> VoiceConfigRead:
        result = await self._voice_configs.update(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            payload=payload,
        )
        await self._advance_bound_agent_drafts(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            voice_config_revision=result.revision,
        )
        return result

    async def patch_section(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        section: str,
        data: Any,
        expected_revision: int,
    ) -> VoiceConfigRead:
        result = await self._voice_configs.patch_section(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            section=section,
            data=data,
            expected_revision=expected_revision,
        )
        await self._advance_bound_agent_drafts(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            voice_config_revision=result.revision,
        )
        return result

    async def delete(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> None:
        bound_agent = await self._db.scalar(
            select(AgentsModel.id).where(
                AgentsModel.organization_id == organization_id,
                AgentsModel.voice_config_id == voice_config_id,
                AgentsModel.lifecycle != DefinitionLifecycle.ARCHIVED.value,
                AgentsModel.deleted.is_(False),
            )
        )
        if bound_agent is not None:
            raise VoiceConfigInUse(
                "Unbind this Voice Config from every active Agent before deleting it."
            )
        await self._voice_configs.delete(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )

    async def _advance_bound_agent_drafts(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        voice_config_revision: int,
    ) -> None:
        rows = await self._db.scalars(
            select(AgentsModel)
            .where(
                AgentsModel.organization_id == organization_id,
                AgentsModel.voice_config_id == voice_config_id,
                AgentsModel.lifecycle != DefinitionLifecycle.ARCHIVED.value,
                AgentsModel.deleted.is_(False),
            )
            .order_by(AgentsModel.id)
            .with_for_update()
        )
        for agent in rows.all():
            state = DefinitionHeaderState(
                lifecycle=DefinitionLifecycle(agent.lifecycle),
                published_revision=agent.published_revision,
                draft_version=agent.draft_version,
                draft_dirty=agent.draft_dirty,
            ).edit(expected_draft_version=agent.draft_version)
            agent.lifecycle = state.lifecycle.value
            agent.published_revision = state.published_revision
            agent.draft_version = state.draft_version
            agent.draft_dirty = state.draft_dirty
            agent.voice_config_revision = voice_config_revision
        await self._db.flush()


__all__ = ["VoiceConfigurationService"]
