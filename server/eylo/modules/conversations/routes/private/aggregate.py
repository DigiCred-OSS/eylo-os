"""HTTP routes for the `conversations` domain."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.conversations.controllers.aggregates import (
    ConversationAggregateController,
)
from eylo.modules.conversations.schemas.aggregates import (
    ConversationAggregateBulkRequest,
    ConversationAggregateBulkResponse,
    ConversationAggregateResponse,
)

# ====================== Aggregate Router ======================
# Separate router to avoid FastAPI path conflicts with /{conversation_id}

aggregate_router = APIRouter(
    prefix="/{organization_id}/aggregate",
    tags=["Aggregates"],
)


@aggregate_router.get(
    "/conversations/{conversation_id}", response_model=ConversationAggregateResponse
)
async def get_conversation_aggregate(
    organization_id: UUID,
    conversation_id: UUID,
    include_messages: bool = Query(
        default=True, description="Include messages in response"
    ),
    message_limit: int = Query(
        default=50, ge=1, le=500, description="Max messages to return"
    ),
    include_participants: bool = Query(
        default=True, description="Include participants in response"
    ),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ConversationAggregateResponse:
    """Get a single conversation with all related data (contact, agents, messages, participants).

    This endpoint returns denormalized conversation data in a single response,
    eliminating the need for multiple API calls to fetch related entities.

    Path: /api/{org_id}/aggregate/conversations/{conversation_id}

    Args:
    ----
        organization_id (UUID): The ID of the organization
        conversation_id (UUID): The ID of the conversation
        include_messages (bool): Whether to include messages (default: True)
        message_limit (int): Maximum number of messages to return (default: 50, max: 500)
        include_participants (bool): Whether to include participants (default: True)
        current_user: The authenticated user

    Returns:
    -------
        ConversationAggregateResponse: Conversation with all related data

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)

    async with start_transaction(ro=True) as db:
        controller = ConversationAggregateController(db)
        return await controller.get_conversation_aggregate(
            conversation_id=conversation_id,
            organization_id=current_user.organization_id,
            include_messages=include_messages,
            message_limit=message_limit,
            include_participants=include_participants,
        )


@aggregate_router.post(
    "/conversations", response_model=ConversationAggregateBulkResponse
)
async def get_conversations_aggregate_bulk(
    organization_id: UUID,
    request: ConversationAggregateBulkRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ConversationAggregateBulkResponse:
    """Get multiple conversations with all related data in a single request.

    This endpoint is optimized for bulk fetching of conversation aggregates,
    using efficient database queries to minimize round-trips.

    Path: POST /api/{org_id}/aggregate/conversations

    Args:
    ----
        organization_id (UUID): The ID of the organization
        request (ConversationAggregateBulkRequest): Bulk request with conversation IDs and options
        current_user: The authenticated user

    Returns:
    -------
        ConversationAggregateBulkResponse: List of conversations with related data

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)

    async with start_transaction(ro=True) as db:
        controller = ConversationAggregateController(db)
        return await controller.get_conversations_aggregate_bulk(
            request=request,
            organization_id=current_user.organization_id,
        )
