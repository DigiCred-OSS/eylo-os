"""Serve participant queries for the active conversation."""

from eylo.modules.conversations.controllers.ws_participants import (
    ParticipantWsController,
)
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsRequestEvent,
)
from eylo.pipelines.websocket.singleton import S_ws_manager


async def handle_participant_query(event: WsRequestEvent, ctx: SessionContext):
    contact_id = await S_ws_manager.get_contact_for_session(
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
    )
    return await ParticipantWsController().handle_participant_query(
        event,
        ctx,
        contact_id,
    )
