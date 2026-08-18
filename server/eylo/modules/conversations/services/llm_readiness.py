"""Conversation-level orchestration for LLM readiness checks."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.modules.agents.services.llm_readiness import AgentLLMReadinessService
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.repositories.conversations import ConversationRepository
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)


class ConversationLLMReadinessService:
    """Resolve the primary agent config before a user message is persisted."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        *,
        participants: ConversationParticipantService | None = None,
        agent_readiness: AgentLLMReadinessService | None = None,
    ) -> None:
        self._conversations = ConversationRepository(db)
        self._participants = participants or ConversationParticipantService(db)
        self._agent_readiness = agent_readiness or AgentLLMReadinessService(db)

    async def ensure_ready(self, conversation_id: UUID) -> None:
        conversation = await self._conversations.get_(conversation_id)
        if conversation is None:
            raise ConversationNotFound

        participants = await self._participants.list_by_conversation(conversation_id)
        agents = self._participants.filter_primary_agent_participant(participants)
        if not agents:
            agents = self._participants.filter_agent_participants(participants)
        if not agents:
            raise AgentNotFoundError("Conversation has no agent participant")

        await self._agent_readiness.ensure_agent_ready(
            organization_id=conversation.organization_id,
            agent_id=UUID(str(agents[0].entity_id)),
        )
