"""Acknowledge WebSocket liveness probes for the current session."""

import arrow
from fastapi import status

from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsEventAction,
    WsPingEvent,
    WsRequestEvent,
    WsResponse,
)

from .error import handle_error
from .log import logger


async def handle_ping(event: WsRequestEvent, ctx: SessionContext) -> WsResponse:
    """Handle ping events (heartbeat requests)."""
    try:
        request = WsPingEvent.model_validate(event.data or {})

        # Create pong response
        return WsResponse(
            status=status.HTTP_200_OK,
            kind=WsEventAction.PONG,
            data={
                "timestamp": request.timestamp,
                "server_time": arrow.utcnow().timestamp(),
            },
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            request_id=event.request_id,
        )
    except Exception as error:
        logger.error("Ping handling failed error_type=%s", type(error).__name__)
        return await handle_error(event, ctx)
