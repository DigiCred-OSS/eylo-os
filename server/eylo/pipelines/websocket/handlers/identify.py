"""Bind a validated contact identity to the current WebSocket session."""

from typing import Optional

from eylo.modules.contacts.controllers.ws_controller import ContactWsController
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsRequestEvent,
    WsResponse,
)


async def handle_identify(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Handle client identification events (linking contact to session)."""
    return await ContactWsController().handle_identify(event, ctx)
