"""Route message queries, creation, and feedback over WebSocket."""

import logging
from typing import Optional
from uuid import UUID

from eylo.modules.conversations.controllers.ws_messages import MessageWsController
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsEventAction,
    WsRequestEvent,
    WsResponse,
)
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


async def handle_message_query(event: WsRequestEvent, ctx: SessionContext):
    contact_id = await _get_session_contact_id(ctx)
    return await MessageWsController().handle_message_query(event, ctx, contact_id)


async def handle_message(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Handle text message events."""
    contact_id = await _get_session_contact_id(ctx)
    response = await MessageWsController().handle_message(event, ctx, contact_id)
    if (
        response
        and response.status == 200
        and response.kind == WsEventAction.MESSAGE_CREATED
        and isinstance(response.data, dict)
        and response.data.get("conversationId")
    ):
        try:
            await S_ws_manager.associate_conversation_session(
                UUID(str(response.data["conversationId"])),
                session_id=ctx.session_id,
                organization_id=ctx.organization_id,
            )
        except Exception as error:
            logger.error(
                "WebSocket conversation association failed "
                "organization_id=%s error_type=%s",
                ctx.organization_id,
                type(error).__name__,
            )
    return response


async def handle_message_feedback(event: WsRequestEvent, ctx: SessionContext):
    contact_id = await _get_session_contact_id(ctx)
    return await MessageWsController().handle_message_feedback(event, ctx, contact_id)


async def _get_session_contact_id(ctx: SessionContext):
    return await S_ws_manager.get_contact_for_session(
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
    )
