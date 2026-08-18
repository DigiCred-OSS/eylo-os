"""Call Lifecycle WebSocket Events

Broadcasts call lifecycle state changes to WebSocket clients in real-time,
enabling the frontend/widget to show accurate call status (ringing, connected, ended).

Architecture:
- Listens for internal call events emitted via `emit_ephemeral()`
- Maps each CallState to a WsEventAction.CALL_* action
- Broadcasts via S_ws_manager to the appropriate session

Follows the same pattern as voice_lifecycle.py (STT/TTS/WebRTC state broadcasting).
"""

import logging
from typing import Any

import arrow

from eylo.events.schema.py_events.call import (
    CallConnectedEvent,
    CallEndedEvent,
    CallRingingEvent,
    CallStartedEvent,
    CallState,
    CallStateEvent,
    CallTransferredEvent,
    CallTransferringEvent,
)
from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)

CALL_STATE_ACTION_MAP = {
    CallState.STARTED: WsEventAction.CALL_STARTED,
    CallState.RINGING: WsEventAction.CALL_RINGING,
    CallState.CONNECTED: WsEventAction.CALL_CONNECTED,
    CallState.ENDED: WsEventAction.CALL_ENDED,
    CallState.TRANSFERRING: WsEventAction.CALL_TRANSFERRING,
    CallState.TRANSFERRED: WsEventAction.CALL_TRANSFERRED,
}


async def _broadcast_call_event(
    event: CallStateEvent, extra: dict[str, Any] | None = None
) -> None:
    """Shared broadcaster for all call state events.

    Args:
        event: The call lifecycle event to broadcast.
        extra: Additional payload fields (avoids mutating the shared event.data).

    """
    action = CALL_STATE_ACTION_MAP.get(event.state)
    if not action:
        logger.warning(f"Unknown call state: {event.state}")
        return

    payload: dict[str, Any] = {
        "message": event.message,
        "state": event.state.value,
        "call_sid": event.call_sid,
        "direction": event.direction.value,
        "provider": event.provider,
        "timestamp": arrow.utcnow().timestamp(),
        **event.data,
    }
    if extra:
        payload.update(extra)

    if event.agent_id:
        payload["agent_id"] = str(event.agent_id)
    if event.conversation_id:
        payload["conversation_id"] = str(event.conversation_id)
    if event.from_number:
        payload["from_number"] = event.from_number
    if event.to_number:
        payload["to_number"] = event.to_number

    try:
        await S_ws_manager.send_response(
            {"kind": action, "data": payload},
            event.organization_id,
            event.session_id,
        )
        logger.debug(
            f"Broadcast call {event.state.value} event for session {event.session_id}"
        )
    except Exception as error:
        logger.error(
            "Call event broadcast failed state=%s error_type=%s",
            event.state.value,
            type(error).__name__,
        )


async def handle_call_started(event: CallStartedEvent) -> None:
    """Broadcast when a call is initiated."""
    await _broadcast_call_event(event)


async def handle_call_ringing(event: CallRingingEvent) -> None:
    """Broadcast when phone is ringing (outbound)."""
    await _broadcast_call_event(event)


async def handle_call_connected(event: CallConnectedEvent) -> None:
    """Broadcast when call is connected and media is active."""
    await _broadcast_call_event(event)


async def handle_call_ended(event: CallEndedEvent) -> None:
    """Broadcast when call terminates, including ended_reason for analytics."""
    extra: dict[str, Any] = {"ended_reason": event.ended_reason}
    if event.duration_seconds is not None:
        extra["duration_seconds"] = event.duration_seconds
    await _broadcast_call_event(event, extra=extra)


async def handle_call_transferring(event: CallTransferringEvent) -> None:
    """Broadcast when a call transfer is initiated."""
    await _broadcast_call_event(event, extra={"transfer_to": event.transfer_to})


async def handle_call_transferred(event: CallTransferredEvent) -> None:
    """Broadcast when a call transfer completes."""
    await _broadcast_call_event(event, extra={"transfer_to": event.transfer_to})
