"""Public exports for the `conversations` domain package."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.conversations.controllers.conversations import ConversationController
from eylo.modules.conversations.controllers.messages import MessageController
from eylo.modules.conversations.controllers.participants import ParticipantController
from eylo.modules.conversations.operator_service import ConversationOperatorService
from eylo.modules.conversations.schemas.conversations import (
    ConversationApiResponseSchema,
    ConversationFilterSchema,
    ConversationsPaginated,
)
from eylo.modules.conversations.schemas.messages import ConversationMessagesPaginated
from eylo.modules.conversations.schemas.participants import (
    ConversationParticipantsPaginated,
)

from .dependencies import parse_conversation_list_filters

router = APIRouter(
    prefix="/{organization_id}/conversations",
    tags=["Conversations"],
)


@router.get("", response_model=ConversationsPaginated)
async def list_conversations(
    organization_id: UUID,
    filters: Annotated[
        ConversationFilterSchema,
        Depends(parse_conversation_list_filters),
    ],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List conversations with pagination for a specific user.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        user_id (UUID): The ID of the user
        pagination (PaginationParams): Pagination parameters
        sort (str, optional): Sort order, either 'asc' or 'desc'. Defaults to 'desc'.

    Returns:
    -------
        ConversationsPaginated: The paginated conversations response

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction(ro=True) as db:
        result = await ConversationOperatorService(db).list(
            offset=pagination.get_offset(),
            limit=pagination.limit,
            organization_id=current_user.organization_id,
            filters=filters,
        )
        return ConversationsPaginated(
            data=result.items,
            total=result.total,
            page=pagination.page,
            limit=pagination.limit,
            has_more=pagination.get_offset() + len(result.items) < result.total,
        )


@router.get("/{conversation_id}", response_model=ConversationApiResponseSchema)
async def get_conversation(
    organization_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ConversationApiResponseSchema:
    """Get a conversation by ID.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        conversation_id (UUID): The ID of the conversation to get

    Returns:
    -------
        ConversationApiResponseSchema: The conversation response with status

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction(ro=True) as db:
        controller = ConversationController(db)
        return await controller.get_conversation(
            organization_id=current_user.organization_id,
            conversation_id=conversation_id,
        )


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesPaginated)
async def get_conversation_messages(
    organization_id: UUID,
    conversation_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> Optional[ConversationMessagesPaginated]:
    """Get paginated messages for a conversation.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        conversation_id (UUID): UUID of the conversation
        pagination: Pagination parameters (page and limit)

    Returns:
    -------
        ConversationMessagesPaginated: Paginated list of messages with status and error information

    """
    return await MessageController().get_conversation_messages(
        organization_id=organization_id,
        conversation_id=conversation_id,
        pagination=pagination,
        current_user=current_user,
    )


@router.get(
    "/{conversation_id}/participants", response_model=ConversationParticipantsPaginated
)
async def get_conversation_participants(
    organization_id: UUID,
    conversation_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> Optional[ConversationParticipantsPaginated]:
    """Get paginated participants for a conversation.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        conversation_id (UUID): UUID of the conversation
        pagination: Pagination parameters (page and limit)

    Returns:
    -------
        ConversationParticipantsPaginated: Paginated list of messages with status and error information

    """
    return await ParticipantController().get_conversation_participants(
        organization_id=organization_id,
        conversation_id=conversation_id,
        pagination=pagination,
        current_user=current_user,
    )
