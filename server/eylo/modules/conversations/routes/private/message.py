"""HTTP routes for the `conversations` domain."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.conversations.controllers.messages import MessageController
from eylo.modules.conversations.schemas.conversations import (
    ConversationFilterSchema,
)
from eylo.modules.conversations.schemas.messages import (
    ConversationMessagesPaginated,
    MessageApiResponseSchema,
    MessageRequestFeedback,
)

from .dependencies import require_conversation_filters

# Message Router
message_router = APIRouter(
    prefix="/{organization_id}/messages",
    tags=["Messages"],
)


@message_router.get("", response_model=ConversationMessagesPaginated)
async def list_conversation_messages(
    organization_id: UUID,
    filters: Annotated[
        ConversationFilterSchema,
        Depends(require_conversation_filters),
    ],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> Optional[ConversationMessagesPaginated]:
    """Get paginated messages for a conversation.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        pagination: Pagination parameters (page and limit)

    Returns:
    -------
        ConversationMessagesPaginated: Paginated list of messages with status and error information

    """
    return await MessageController().list_conversation_messages(
        organization_id=organization_id,
        filters=filters,
        pagination=pagination,
        current_user=current_user,
    )


@message_router.post("/feedback", response_model=MessageApiResponseSchema)
async def submit_message_feedback(
    organization_id: UUID,
    request_id: UUID,
    feedback: MessageRequestFeedback,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Submit feedback for a message."""
    return await MessageController().submit_message_feedback(
        organization_id=organization_id,
        request_id=request_id,
        feedback=feedback,
        current_user=current_user,
    )
