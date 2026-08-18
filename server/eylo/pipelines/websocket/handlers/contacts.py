"""Serve contact queries for the authenticated WebSocket session."""

from eylo.modules.contacts.controllers.ws_controller import ContactWsController
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsRequestEvent,
)


async def handle_contact_query(event: WsRequestEvent, ctx: SessionContext):
    return await ContactWsController().handle_contact_query(event, ctx)
