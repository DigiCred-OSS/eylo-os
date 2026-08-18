"""Read the exact voice stack carried by one published Agent revision."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.modules.agents.models import AgentsModel
from eylo.modules.agents.schemas.api import (
    AgentEffectiveVoiceStackResponseSchema,
    AgentRevisionReferenceSchema,
    AgentVoiceStackState,
)
from eylo.modules.agents.services.revisions import AgentRevisionService


class AgentEffectiveVoiceStackService:
    """Project immutable publication authority for the admin console."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()

    async def get(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
    ) -> AgentEffectiveVoiceStackResponseSchema:
        header = await self._db.scalar(
            select(AgentsModel).where(
                AgentsModel.organization_id == organization_id,
                AgentsModel.id == agent_id,
                AgentsModel.deleted.is_(False),
            )
        )
        if header is None:
            raise AgentNotFoundError("Agent not found.")
        if header.published_revision is None:
            return AgentEffectiveVoiceStackResponseSchema(
                agent_id=agent_id,
                state=AgentVoiceStackState.NOT_PUBLISHED,
            )

        revision = await AgentRevisionService(self._db).get_revision(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=header.published_revision,
        )
        if revision.voice_config_id is None:
            state = AgentVoiceStackState.TEXT_ONLY
        elif revision.realtime_provider_config_id is not None:
            state = AgentVoiceStackState.REALTIME
        else:
            state = AgentVoiceStackState.DECOMPOSED

        return AgentEffectiveVoiceStackResponseSchema(
            agent_id=agent_id,
            agent_revision=revision.revision,
            state=state,
            voice_config=_reference(
                revision.voice_config_id,
                revision.voice_config_revision,
            ),
            webrtc_provider=_reference(
                revision.webrtc_provider_config_id,
                revision.webrtc_provider_config_revision,
            ),
            stt_provider=_reference(
                revision.stt_provider_config_id,
                revision.stt_provider_config_revision,
            ),
            tts_provider=_reference(
                revision.tts_provider_config_id,
                revision.tts_provider_config_revision,
            ),
            realtime_provider=_reference(
                revision.realtime_provider_config_id,
                revision.realtime_provider_config_revision,
            ),
            storage_provider=_reference(
                revision.storage_provider_config_id,
                revision.storage_provider_config_revision,
            ),
        )


def _reference(
    config_id: UUID | None,
    revision: int | None,
) -> AgentRevisionReferenceSchema | None:
    if config_id is None and revision is None:
        return None
    if config_id is None or revision is None:
        raise RuntimeError("Published Agent contains an incomplete revision reference.")
    return AgentRevisionReferenceSchema(id=config_id, revision=revision)


__all__ = ["AgentEffectiveVoiceStackService"]
