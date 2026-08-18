"""Transport orchestration for the `conversations` domain."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.aggregates import (
    ConversationAggregateBulkRequest,
    ConversationAggregateBulkResponse,
    ConversationAggregateResponse,
)
from eylo.modules.conversations.services.aggregates import (
    ConversationAggregateService,
)
from eylo.modules.conversations.services.conversations import ConversationService


class ConversationAggregateController:
    """Controller for conversation aggregate operations.

    Handles HTTP requests for fetching conversations with related data
    (contacts, agents, messages, participants) in single API calls.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize controller with database session.

        Args:
            db_session: SQLAlchemy async session

        """
        self.db_session = db_session
        self.service = ConversationAggregateService(self.db_session)
        self.conversation_service = ConversationService(self.db_session)

    async def get_conversation_aggregate(
        self,
        conversation_id: UUID,
        organization_id: UUID,
        include_messages: bool = True,
        message_limit: int = 50,
        include_participants: bool = True,
    ) -> ConversationAggregateResponse:
        """Get a single conversation with all related data.

        Args:
            conversation_id: Conversation UUID
            organization_id: Organization UUID (for multi-tenancy)
            include_messages: Whether to include messages
            message_limit: Maximum number of messages
            include_participants: Whether to include participants

        Returns:
            ConversationAggregateResponse with denormalized data

        Raises:
            HTTPException: 404 if conversation not found

        """
        try:
            conversation = await self.conversation_service.get_by_organization_and_id(
                organization_id=organization_id,
                pk=conversation_id,
            )
        except ConversationNotFound:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        aggregate = await self.service.get_conversation_with_relations(
            conversation_id=conversation.id,
            organization_id=organization_id,
            include_messages=include_messages,
            message_limit=message_limit,
            include_participants=include_participants,
        )

        if not aggregate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Map InDb schema to API response schema
        return ConversationAggregateResponse(
            id=aggregate.id,
            organization_id=aggregate.organization_id,
            external_id=aggregate.external_id,
            channel=aggregate.channel,
            status=aggregate.status,
            title=aggregate.title,
            has_triggered_title_generation=aggregate.has_triggered_title_generation,
            ended_at=aggregate.ended_at,
            swarm_id=aggregate.swarm_id,
            swarm_revision=aggregate.swarm_revision,
            meta=aggregate.meta,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
            contact=aggregate.contact,
            primary_agent=aggregate.primary_agent,
            all_agents=aggregate.all_agents,
            participants=aggregate.participants,
            messages=aggregate.messages,
            message_count=aggregate.message_count,
        )

    async def get_conversations_aggregate_bulk(
        self,
        request: ConversationAggregateBulkRequest,
        organization_id: UUID,
    ) -> ConversationAggregateBulkResponse:
        """Get multiple conversations with all related data.

        Args:
            request: Bulk request with conversation IDs and options
            organization_id: Organization UUID

        Returns:
            ConversationAggregateBulkResponse with list of aggregates

        Raises:
            HTTPException: 400 if request validation fails

        """
        if not request.conversation_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_ids cannot be empty",
            )

        if len(request.conversation_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot fetch more than 100 conversations at once",
            )

        requested_ids = set(request.conversation_ids)
        conversations = await self.conversation_service.list_by_ids(
            conversation_ids=list(requested_ids),
            organization_id=organization_id,
        )
        resolved_ids = {conversation.id for conversation in conversations}
        if resolved_ids != requested_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        aggregates = await self.service.get_conversations_with_relations(
            conversation_ids=list(resolved_ids),
            organization_id=organization_id,
            include_messages=request.include_messages,
            message_limit=request.message_limit or 50,
            include_participants=request.include_participants,
        )

        # Map InDb schemas to API response schemas
        responses = [
            ConversationAggregateResponse(
                id=agg.id,
                organization_id=agg.organization_id,
                external_id=agg.external_id,
                channel=agg.channel,
                status=agg.status,
                title=agg.title,
                has_triggered_title_generation=agg.has_triggered_title_generation,
                ended_at=agg.ended_at,
                swarm_id=agg.swarm_id,
                swarm_revision=agg.swarm_revision,
                meta=agg.meta,
                created_at=agg.created_at,
                updated_at=agg.updated_at,
                contact=agg.contact,
                primary_agent=agg.primary_agent,
                all_agents=agg.all_agents,
                participants=agg.participants,
                messages=agg.messages,
                message_count=agg.message_count,
            )
            for agg in aggregates
        ]

        return ConversationAggregateBulkResponse(
            conversations=responses,
            total=len(responses),
        )
