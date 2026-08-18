"""Public exports for the `websocket` pipeline package."""

import logging
from typing import (
    Awaitable,
    Callable,
    Dict,
    Optional,
)

from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.handlers.contacts import handle_contact_query
from eylo.pipelines.websocket.handlers.participants import handle_participant_query
from eylo.pipelines.websocket.schemas import (
    WsEventAction,
    WsRequestEvent,
    WsResponse,
)

from .audio import handle_audio_config, handle_audio_data
from .consent import handle_recording_consent
from .conversation import (
    handle_conversation_query,
    handle_conversation_read,
    handle_start_conversation,
)
from .error import handle_error
from .identify import handle_identify
from .message import handle_message, handle_message_feedback, handle_message_query
from .noop import handle_noop
from .ping import handle_ping
from .webrtc import (
    handle_webrtc_hangup,
    handle_webrtc_ice_candidate,
    handle_webrtc_offer,
    handle_webrtc_prepare,
)

logger = logging.getLogger(__name__)

__PUBLIC_ACTIONS: Dict[
    WsEventAction,
    Callable[[WsRequestEvent, SessionContext], Awaitable[Optional[WsResponse]]],
] = {
    WsEventAction.ACK: handle_noop,
    WsEventAction.PING: handle_ping,
    WsEventAction.ERROR: handle_error,
}


__PRIVATE_ACTIONS: Dict[
    WsEventAction,
    Callable[[WsRequestEvent, SessionContext], Awaitable[Optional[WsResponse]]],
] = {
    # contact
    WsEventAction.CONTACT_IDENTIFIED: handle_identify,
    WsEventAction.CONTACT_QUERY: handle_contact_query,
    # PARTICIPANT
    WsEventAction.PARTICIPANT_QUERY: handle_participant_query,
    # MESSAGE
    WsEventAction.MESSAGE_CREATED: handle_message,
    WsEventAction.MESSAGE_QUERY: handle_message_query,
    WsEventAction.MESSAGE_FEEDBACK: handle_message_feedback,
    # CONVERSATION
    WsEventAction.CONVERSATION_CREATED: handle_start_conversation,
    WsEventAction.CONVERSATION_QUERY: handle_conversation_query,
    WsEventAction.CONVERSATION_READ: handle_conversation_read,
    # AUDIO
    WsEventAction.AUDIO_CONFIG: handle_audio_config,
    WsEventAction.AUDIO_DATA: handle_audio_data,
    # RECORDING CONSENT
    WsEventAction.RECORDING_CONSENT: handle_recording_consent,
    # WEBRTC
    WsEventAction.WEBRTC_PREPARE: handle_webrtc_prepare,
    WsEventAction.WEBRTC_OFFER: handle_webrtc_offer,
    WsEventAction.WEBRTC_ICE_CANDIDATE: handle_webrtc_ice_candidate,
    WsEventAction.WEBRTC_HANGUP: handle_webrtc_hangup,
}


async def handle_event(
    request_payload: dict,
    ctx: SessionContext,
) -> Optional[WsResponse]:
    """Process WebSocket events based on their kind using a handler map."""
    event = WsRequestEvent.from_dict(request_payload)

    handler = None

    if event.kind in __PUBLIC_ACTIONS:
        handler = __PUBLIC_ACTIONS.get(event.kind)
    elif event.kind in __PRIVATE_ACTIONS:
        if ctx.contact_id:
            handler = __PRIVATE_ACTIONS.get(event.kind)
        else:
            logger.warning(
                "Unauthorized WebSocket event organization_id=%s kind=%s",
                ctx.organization_id,
                event.kind,
            )

            return None

    if handler:
        return await handler(event, ctx)

    logger.warning(f"Unknown event kind received: {event.kind}")
    return None
