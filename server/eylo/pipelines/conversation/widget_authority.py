"""Resolve contact ownership and exact Agent authority for one widget chat."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.conversations import ConversationBaseService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)


@dataclass(frozen=True, slots=True)
class WidgetConversationAuthority:
    organization_id: UUID
    contact_id: UUID
    conversation_id: UUID
    agent_id: UUID
    agent_revision: int


async def resolve_widget_conversation_authority(
    *,
    organization_id: UUID,
    contact_id: UUID,
    conversation_id: UUID,
    session: AsyncSession,
) -> WidgetConversationAuthority:
    """Resolve one contact-owned chat and its single active primary Agent."""
    await ConversationBaseService(session).get_by_organization_contact_and_id(
        organization_id=organization_id,
        contact_id=contact_id,
        pk=conversation_id,
    )
    participants = await ConversationParticipantService(session).list_by_conversation(
        conversation_id
    )
    primary_agents = [
        participant
        for participant in participants
        if participant.entity_kind == ParticipantKind.AGENT
        and participant.is_primary
        and participant.is_active
        and not participant.deleted
        and participant.agent_id is not None
        and participant.agent_revision is not None
    ]
    if len(primary_agents) != 1:
        raise ConversationNotFound
    primary_agent = primary_agents[0]
    return WidgetConversationAuthority(
        organization_id=organization_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        agent_id=primary_agent.agent_id,
        agent_revision=primary_agent.agent_revision,
    )


__all__ = [
    "WidgetConversationAuthority",
    "resolve_widget_conversation_authority",
]
