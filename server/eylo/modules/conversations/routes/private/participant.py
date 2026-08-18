"""HTTP routes for the `conversations` domain."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.conversations.controllers.participants import ParticipantController
from eylo.modules.conversations.schemas.conversations import (
    ConversationFilterSchema,
)
from eylo.modules.conversations.schemas.participants import (
    ConversationParticipantsPaginated,
)

from .dependencies import require_conversation_filters

# Participant Router
participant_router = APIRouter(
    prefix="/{organization_id}/participants",
    tags=["Participants"],
)


@participant_router.get("", response_model=ConversationParticipantsPaginated)
async def list_conversation_participants(
    organization_id: UUID,
    filters: Annotated[
        ConversationFilterSchema,
        Depends(require_conversation_filters),
    ],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> Optional[ConversationParticipantsPaginated]:
    """Get paginated participants for a conversation.

    Args:
    ----
        organization_id (UUID): The ID of the organization
        pagination: Pagination parameters (page and limit)

    Returns:
    -------
        ConversationParticipantsPaginated: Paginated list of messages with status and error information

    """
    return await ParticipantController().list_conversation_participants(
        organization_id=organization_id,
        filters=filters,
        pagination=pagination,
        current_user=current_user,
    )
