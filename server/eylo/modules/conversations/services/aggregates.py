"""Application services for the `conversations` domain."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.services import EyloBaseService
from eylo.modules.conversations.repositories.aggregates import (
    ConversationAggregateRepository,
)
from eylo.modules.conversations.schemas.aggregates import (
    AgentSummary,
    ContactSummary,
    ConversationAggregateResponse,
    MessageSummary,
    ParticipantSummary,
)
from eylo.modules.conversations.schemas.messages import MessageKind


class ConversationAggregateService(EyloBaseService[ConversationAggregateResponse]):
    """Service for conversation aggregate operations.

    Provides methods to fetch conversations with all related data (contacts,
    agents, messages, participants) in a single operation.
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the service with an aggregate repository.

        Args:
            repository: ConversationAggregateRepository instance

        """
        self._repository = ConversationAggregateRepository(db)

    @property
    def schema(self) -> type[ConversationAggregateResponse]:
        """Return the schema class for this service.

        Returns:
            ConversationAggregateResponse schema class

        """
        return ConversationAggregateResponse

    @property
    def repository(self) -> ConversationAggregateRepository:
        """Return the repository instance.

        Returns:
            ConversationAggregateRepository instance

        """
        return self._repository

    async def get_conversation_with_relations(
        self,
        conversation_id: UUID,
        organization_id: UUID,
        include_messages: bool = True,
        message_limit: int = 50,
        message_offset: int = 0,
        include_participants: bool = True,
        message_kinds: list[MessageKind] | None = None,
    ) -> ConversationAggregateResponse | None:
        """Fetch a single conversation with all related data.

        Args:
            conversation_id: Conversation UUID
            organization_id: Organization UUID
            include_messages: Whether to include messages
            message_limit: Max messages to return
            message_offset: Number of messages to skip (for pagination)
            include_participants: Whether to include participants

        Returns:
            ConversationAggregateResponse instance or None if not found

        """
        results = await self.repository.get_aggregates_by_ids(
            conversation_ids=[conversation_id],
            organization_id=organization_id,
            include_messages=include_messages,
            message_limit=message_limit,
            message_offset=message_offset,
            include_participants=include_participants,
            message_kinds=message_kinds,
        )

        if not results:
            return None

        return self._map_dict_to_schema(results[0])

    async def get_conversations_with_relations(
        self,
        conversation_ids: list[UUID],
        organization_id: UUID,
        include_messages: bool = True,
        message_limit: int = 50,
        message_offset: int = 0,
        include_participants: bool = True,
        message_kinds: list[MessageKind] | None = None,
    ) -> list[ConversationAggregateResponse]:
        """Fetch multiple conversations with all related data.

        Args:
            conversation_ids: List of conversation UUIDs
            organization_id: Organization UUID
            include_messages: Whether to include messages
            message_limit: Max messages to return
            message_offset: Number of messages to skip per conversation (for pagination)
            include_participants: Whether to include participants

        Returns:
            List of ConversationAggregateResponse instances

        """
        aggregate_dicts = await self.repository.get_aggregates_by_ids(
            conversation_ids=conversation_ids,
            organization_id=organization_id,
            include_messages=include_messages,
            message_limit=message_limit,
            message_offset=message_offset,
            include_participants=include_participants,
            message_kinds=message_kinds,
        )

        return [self._map_dict_to_schema(agg_dict) for agg_dict in aggregate_dicts]

    def _map_dict_to_schema(
        self, aggregate_dict: dict
    ) -> ConversationAggregateResponse:
        """Map repository aggregate dict to ConversationAggregateResponse schema.

        Args:
            aggregate_dict: Dictionary from repository

        Returns:
            ConversationAggregateResponse instance

        """
        conversation = aggregate_dict["conversation"]
        contact = aggregate_dict["contact"]
        primary_agent = aggregate_dict["primary_agent"]
        all_agents = aggregate_dict["all_agents"]
        participants_data = aggregate_dict["participants"]
        messages = aggregate_dict["messages"]
        message_count = aggregate_dict["message_count"]

        # Map contact to ContactSummary
        contact_summary = None
        if contact:
            contact_summary = ContactSummary(
                id=contact.id,
                name=contact.name,
                primary_email=contact.primary_email,
                primary_phone=contact.primary_phone,
            )

        # Map primary agent to AgentSummary
        primary_agent_summary = None
        if primary_agent:
            primary_agent_summary = AgentSummary(
                id=primary_agent.id,
                name=primary_agent.name,
                slug=primary_agent.slug,
                status=primary_agent.status.value,
            )

        # Map all agents to AgentSummary
        all_agents_summary = [
            AgentSummary(
                id=agent.id,
                name=agent.name,
                slug=agent.slug,
                status=agent.status.value,
            )
            for agent in all_agents
        ]

        # Map participants to ParticipantSummary
        participants_summary = [
            ParticipantSummary(
                id=p_data["participant"].id,
                entity_kind=p_data["participant"].entity_kind,
                entity_id=p_data["participant"].entity_id,
                has_initiated=p_data["participant"].has_initiated,
                is_active=p_data["participant"].is_active,
                is_primary=p_data["participant"].is_primary,
                joined_at=p_data["participant"].joined_at,
                left_at=p_data["participant"].left_at,
                entity_name=p_data["entity_name"],
            )
            for p_data in participants_data
        ]

        # Map messages to MessageSummary
        messages_summary = [
            MessageSummary(
                id=msg.id,
                kind=msg.kind,
                content_kind=msg.content_kind,
                content=msg.content,
                sender_participant_id=msg.sender_participant_id,
                request_id=msg.request_id,
                request_feedback=msg.request_feedback,
                sender_kind=next(
                    (
                        p["participant"].entity_kind
                        for p in participants_data
                        if p["participant"].id == msg.sender_participant_id
                    ),
                    None,
                ),
                created_at=msg.created_at,
            )
            for msg in messages
        ]

        # Build ConversationAggregateResponse
        return ConversationAggregateResponse(
            id=conversation.id,
            organization_id=conversation.organization_id,
            external_id=conversation.external_id,
            channel=conversation.channel,
            status=conversation.status,
            title=conversation.title,
            has_triggered_title_generation=(
                conversation.has_triggered_title_generation or False
            ),
            ended_at=conversation.ended_at,
            swarm_id=conversation.swarm_id,
            swarm_revision=conversation.swarm_revision,
            meta=conversation.meta,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            contact=contact_summary,
            primary_agent=primary_agent_summary,
            all_agents=all_agents_summary,
            participants=participants_summary,
            messages=messages_summary,
            message_count=message_count,
        )
