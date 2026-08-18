"""Transport orchestration for the `conversations` domain."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.conversations import (
    ConversationApiResponseSchema,
    ConversationFilterSchema,
    ConversationMessageRequest,
    ConversationStartRequest,
)
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.conversations.services.messages import MessageService
from eylo.pipelines.conversation.start import start_conversation_for_new_work


class ConversationController:
    """ConversationController behavior for the "conversations" domain."""

    def __init__(self, db: AsyncSession | None = None):
        """Init for the "conversations" domain."""
        self.conversation_service = ConversationService(db)
        self.message_service = MessageService(db)
        self.db = db

    async def list_conversations(
        self,
        limit: int,
        offset: int,
        organization_id: UUID,
        filters: ConversationFilterSchema | None = None,
    ) -> list[ConversationApiResponseSchema]:
        """List User Conversations."""
        # If conversation for specific agent requested, fetch only those
        if filters:
            if filters.agent_id:
                conversations = await self.conversation_service.list_by_agent_id(
                    agent_id=filters.agent_id,
                    organization_id=organization_id,
                    limit=limit,
                    offset=offset,
                )
                return [
                    ConversationApiResponseSchema.model_validate(c)
                    for c in conversations
                ]

        # If specific conversation IDs requested, fetch only those
        if filters and filters.conversation_ids:
            conversations = await self.conversation_service.list_by_ids(
                conversation_ids=filters.conversation_ids,
                organization_id=organization_id,
            )
            return [
                ConversationApiResponseSchema.model_validate(c) for c in conversations
            ]

        # Otherwise, paginated list
        conversations = await self.conversation_service.list_by_organization(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            filters=filters,
        )
        return [ConversationApiResponseSchema.model_validate(c) for c in conversations]

    async def count_conversations(
        self,
        organization_id: UUID,
    ) -> int:
        return await self.conversation_service.count_by_organization(
            organization_id=organization_id,
        )

    async def get_conversation(
        self, organization_id: UUID, conversation_id: UUID
    ) -> ConversationApiResponseSchema:
        """Get Conversation Details."""
        try:
            # Get the conversation using the service
            conversation = await self.conversation_service.get_by_organization_and_id(
                organization_id=organization_id,
                pk=conversation_id,
            )
            return ConversationApiResponseSchema.model_validate(conversation)
        except ConversationNotFound:
            raise HTTPException(status_code=404)

    async def start_conversation(
        self, organization_id: UUID, request: ConversationStartRequest
    ):
        """Start New Conversation."""
        return await start_conversation_for_new_work(
            service=self.conversation_service,
            organization_id=organization_id,
            request=request,
            db=self.db,
        )

    async def send_message(
        self, conversation_id: UUID, request: ConversationMessageRequest
    ):
        pass
