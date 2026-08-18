"""Resolve immutable execution authority before creating a conversation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agents.domain import InvalidSwarmDefinitionError
from eylo.modules.conversations.schemas.conversations import ConversationStartRequest
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.conversations import ConversationBaseService
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agents import (
    build_executable_agent_resolver,
    build_executable_swarm_resolver,
)


async def start_conversation_for_new_work(
    *,
    service: ConversationBaseService,
    organization_id: UUID,
    request: ConversationStartRequest,
    db: AsyncSession | None = None,
    consumer_kind: TemplateConsumerKind = TemplateConsumerKind.CONVERSATIONAL_TEXT,
):
    """Resolve the published agent or swarm once, then persist exact refs."""
    participant_kinds = {request.from_.kind, request.to_.kind}
    if participant_kinds != {ParticipantKind.AGENT, ParticipantKind.CONTACT}:
        raise ValueError(
            "Conversation participants must include one AGENT and one CONTACT."
        )
    agent = request.to_ if request.to_.kind is ParticipantKind.AGENT else request.from_
    if agent.id is None:
        raise ValueError("Agent participants require an explicit agent id.")

    resolved_swarm = None
    if request.swarm_id is not None:
        resolved_swarm = await build_executable_swarm_resolver(db).resolve_for_new_work(
            organization_id=organization_id,
            swarm_id=request.swarm_id,
            consumer_kind=consumer_kind,
        )
        entry_member = resolved_swarm.member_by_agent_id(agent.id)
        if entry_member is None:
            raise InvalidSwarmDefinitionError(
                "The selected entry agent is not in this swarm topology."
            )
        resolved_agent = entry_member.executable_agent
    else:
        resolved_agent = await build_executable_agent_resolver(db).resolve_for_new_work(
            organization_id=organization_id,
            agent_id=agent.id,
            consumer_kind=consumer_kind,
        )

    return await service.start_conversation(
        organization_id=organization_id,
        request=request,
        resolved_agent=resolved_agent,
        resolved_swarm=resolved_swarm,
    )


__all__ = ["start_conversation_for_new_work"]
