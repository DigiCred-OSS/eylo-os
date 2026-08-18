"""Controller for handling conversation participant-related operations."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.conversations import ConversationFilterSchema
from eylo.modules.conversations.schemas.participants import (
    ConversationParticipantsPaginated,
    ParticipantApiResponseSchema,
)
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)


class ParticipantController:
    """Controller for handling conversation participant-related operations."""

    def __init__(self):
        """Initialize the ParticipantController."""
        self.service = ConversationParticipantService()

    async def get_conversation_participants(
        self,
        organization_id: UUID,
        conversation_id: UUID,
        pagination: Annotated[PaginationParams, Depends(get_pagination)],
        current_user: CurrentUserSchema,
    ) -> Optional[ConversationParticipantsPaginated]:
        """Get paginated participants for a conversation."""
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=404)

        async with start_transaction(ro=True) as db:
            try:
                await ConversationService(db).get_by_organization_and_id(
                    organization_id=current_user.organization_id,
                    pk=conversation_id,
                )
            except ConversationNotFound:
                raise HTTPException(status_code=404)
            participant_service = ConversationParticipantService(db)
            participants = await participant_service.list_page_by_conversation(
                conversation_id=conversation_id,
                limit=pagination.limit,
                offset=pagination.get_offset(),
            )
            total = await participant_service.count_by_conversation(
                conversation_id=conversation_id
            )
            return ConversationParticipantsPaginated(
                data=[
                    ParticipantApiResponseSchema.model_validate(participant)
                    for participant in participants
                ],
                total=total,
                page=pagination.page,
                limit=pagination.limit,
                has_more=pagination.get_offset() + len(participants) < total,
            )

    async def list_conversation_participants(
        self,
        organization_id: UUID,
        filters: Annotated[ConversationFilterSchema, Query()],
        pagination: Annotated[PaginationParams, Depends(get_pagination)],
        current_user: CurrentUserSchema,
    ) -> Optional[ConversationParticipantsPaginated]:
        """Get paginated participants for a list of conversations."""
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=404)

        if not filters.conversation_ids:
            raise HTTPException(
                status_code=400, detail="conversation_ids filter is required"
            )
        async with start_transaction(ro=True) as db:
            requested_conversation_ids = set(filters.conversation_ids)
            conversations = await ConversationService(db).list_by_ids(
                conversation_ids=list(requested_conversation_ids),
                organization_id=current_user.organization_id,
            )
            resolved_conversation_ids = {conversation.id for conversation in conversations}
            if resolved_conversation_ids != requested_conversation_ids:
                raise HTTPException(status_code=404)
            participant_service = ConversationParticipantService(db)
            participants = await participant_service.list_page_by_conversations(
                conversation_ids=list(resolved_conversation_ids),
                limit=pagination.limit,
                offset=pagination.get_offset(),
            )
            total = await participant_service.count_by_conversations(
                conversation_ids=list(resolved_conversation_ids),
            )
            return ConversationParticipantsPaginated(
                data=[
                    ParticipantApiResponseSchema.model_validate(participant)
                    for participant in participants
                ],
                total=total,
                page=pagination.page,
                limit=pagination.limit,
                has_more=pagination.get_offset() + len(participants) < total,
            )
