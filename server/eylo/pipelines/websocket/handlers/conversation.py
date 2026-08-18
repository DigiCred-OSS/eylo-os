"""Route conversation list, read, and start commands for a contact."""

from uuid import UUID

from eylo.modules.conversations.controllers.ws_conversations import (
    ConversationWsController,
)
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsEventAction,
    WsRequestEvent,
    WsResponse,
)
from eylo.pipelines.websocket.singleton import S_ws_manager


async def handle_conversation_query(event: WsRequestEvent, ctx: SessionContext):
    """Handle conversation query using aggregate service for efficient data fetching.

    Returns conversations with all related data (contacts, agents, messages, participants)
    in a single response to minimize round-trips.
    """
    contact_id = await _get_session_contact_id(ctx)
    return await ConversationWsController().handle_conversation_aggregate_query(
        event,
        ctx,
        contact_id,
    )


async def handle_conversation_read(event: WsRequestEvent, ctx: SessionContext):
    contact_id = await _get_session_contact_id(ctx)
    response = await ConversationWsController().handle_conversation_read(
        event,
        ctx,
        contact_id,
    )
    if (
        contact_id is not None
        and response.status == 200
        and response.kind == WsEventAction.CONVERSATION_READ
        and isinstance(response.data, dict)
        and response.data.get("conversation_id")
    ):
        await S_ws_manager.reply_to_conversation_contact(
            contact_id=contact_id,
            organization_id=ctx.organization_id,
            conversation_id=UUID(str(response.data["conversation_id"])),
            payload=response.data,
            kind=response.kind,
        )
    return response


async def handle_start_conversation(
    event: WsRequestEvent, ctx: SessionContext
) -> WsResponse:
    contact_id = await _get_session_contact_id(ctx)
    response = await ConversationWsController().handle_start_conversation(
        event,
        ctx,
        contact_id,
    )
    if (
        response.status == 200
        and response.kind == WsEventAction.CONVERSATION_CREATED
        and isinstance(response.data, dict)
        and response.data.get("id")
    ):
        await S_ws_manager.associate_conversation_session(
            UUID(str(response.data["id"])),
            session_id=ctx.session_id,
            organization_id=ctx.organization_id,
        )
    return response


async def _get_session_contact_id(ctx: SessionContext):
    return await S_ws_manager.get_contact_for_session(
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
    )
