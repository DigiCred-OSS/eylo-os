"""Project WebRTC, STT, and TTS service state onto WebSocket UI deltas.

These best-effort events describe provider/transport readiness; they do not
control the runtime. The widget applies its service state machines to reject
invalid downgrades. Call interaction state (listening, processing, speaking,
terminal error) uses the separately correlated ``voice:state`` projection.
"""

import logging

import arrow

from eylo.events.schema.py_events.voice import (
    STTState,
    STTStateEvent,
    TTSState,
    TTSStateEvent,
    WebRTCState,
    WebRTCStateEvent,
)
from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)

# Map WebRTC state enum to WebSocket action
WEBRTC_STATE_ACTION_MAP = {
    WebRTCState.PEER_CREATED: WsEventAction.WEBRTC_PEER_CREATED,
    WebRTCState.PEER_CONNECTING: WsEventAction.WEBRTC_PEER_CONNECTING,
    WebRTCState.PEER_CONNECTED: WsEventAction.WEBRTC_PEER_CONNECTED,
    WebRTCState.PEER_DISCONNECTED: WsEventAction.WEBRTC_PEER_DISCONNECTED,
    WebRTCState.PEER_FAILED: WsEventAction.WEBRTC_PEER_FAILED,
    WebRTCState.ICE_GATHERING: WsEventAction.WEBRTC_ICE_GATHERING,
    WebRTCState.ICE_COMPLETE: WsEventAction.WEBRTC_ICE_COMPLETE,
    WebRTCState.TRACK_ADDED: WsEventAction.WEBRTC_TRACK_ADDED,
    WebRTCState.TRACK_REMOVED: WsEventAction.WEBRTC_TRACK_REMOVED,
}

# Map STT state enum to WebSocket action
STT_STATE_ACTION_MAP = {
    STTState.CONNECTING: WsEventAction.STT_CONNECTING,
    STTState.CONNECTED: WsEventAction.STT_CONNECTED,
    STTState.READY: WsEventAction.STT_READY,
    STTState.DISCONNECTED: WsEventAction.STT_DISCONNECTED,
    STTState.ERROR: WsEventAction.STT_ERROR,
}

# Map TTS state enum to WebSocket action
TTS_STATE_ACTION_MAP = {
    TTSState.CONNECTING: WsEventAction.TTS_CONNECTING,
    TTSState.CONNECTED: WsEventAction.TTS_CONNECTED,
    TTSState.READY: WsEventAction.TTS_READY,
    TTSState.DISCONNECTED: WsEventAction.TTS_DISCONNECTED,
    TTSState.ERROR: WsEventAction.TTS_ERROR,
}


async def handle_webrtc_state(event: WebRTCStateEvent):
    """Broadcast WebRTC peer connection state changes to the client.

    Args:
        event: WebRTC state change event containing state, message, and metadata

    """
    # event.state is WebRTCState in this handler
    webrtc_state = event.state if isinstance(event.state, WebRTCState) else None
    if not webrtc_state:
        logger.warning(f"Invalid WebRTC state type: {event.state}")
        return

    action = WEBRTC_STATE_ACTION_MAP.get(webrtc_state)
    if not action:
        logger.warning(f"Unknown WebRTC state: {webrtc_state}")
        return

    event_data = dict(event.data)
    provider_state = event_data.pop("state", None)
    payload = {
        "message": event.message,
        "state": event.state,
        "timestamp": arrow.utcnow().timestamp(),
        **event_data,
    }
    if provider_state is not None:
        payload["provider_state"] = provider_state

    try:
        await S_ws_manager.send_response(
            {"kind": action, "data": payload},
            event.organization_id,
            event.session_id,
        )
        logger.debug(
            f"Broadcast WebRTC {event.state} event for session {event.session_id}"
        )
    except Exception as error:
        logger.error(
            "WebRTC event broadcast failed state=%s error_type=%s",
            event.state,
            type(error).__name__,
        )


async def handle_stt_state(event: STTStateEvent):
    """Broadcast STT service state changes to the client.

    Args:
        event: STT state change event containing state, message, and metadata

    """
    # event.state is STTState in this handler
    stt_state = event.state if isinstance(event.state, STTState) else None
    if not stt_state:
        logger.warning(f"Invalid STT state type: {event.state}")
        return

    action = STT_STATE_ACTION_MAP.get(stt_state)
    if not action:
        logger.warning(f"Unknown STT state: {stt_state}")
        return

    payload = {
        "message": event.message,
        "vendor": event.vendor,
        "timestamp": arrow.utcnow().timestamp(),
        **event.data,  # Include any additional data from the event
    }

    try:
        await S_ws_manager.send_response(
            {"kind": action, "data": payload},
            event.organization_id,
            event.session_id,
        )
        logger.debug(
            f"Broadcast STT {event.state} event for session {event.session_id}"
        )
    except Exception as error:
        logger.error(
            "STT event broadcast failed state=%s error_type=%s",
            event.state,
            type(error).__name__,
        )


async def handle_tts_state(event: TTSStateEvent):
    """Broadcast TTS service state changes to the client.

    Args:
        event: TTS state change event containing state, message, and metadata

    """
    # event.state is TTSState in this handler
    tts_state = event.state if isinstance(event.state, TTSState) else None
    if not tts_state:
        logger.warning(f"Invalid TTS state type: {event.state}")
        return

    action = TTS_STATE_ACTION_MAP.get(tts_state)
    if not action:
        logger.warning(f"Unknown TTS state: {tts_state}")
        return

    payload = {
        "message": event.message,
        "vendor": event.vendor,
        "timestamp": arrow.utcnow().timestamp(),
        **event.data,  # Include any additional data from the event
    }

    try:
        await S_ws_manager.send_response(
            {"kind": action, "data": payload},
            event.organization_id,
            event.session_id,
        )
        logger.debug(
            f"Broadcast TTS {event.state} event for session {event.session_id}"
        )
    except Exception as error:
        logger.error(
            "TTS event broadcast failed state=%s error_type=%s",
            event.state,
            type(error).__name__,
        )
