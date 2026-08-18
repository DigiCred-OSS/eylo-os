"""Recording notification state shared by browser and telephony voice flows.

Recording is part of the primary voice flow. Notification delivery and caller
feedback are observable compliance state, not synchronous data controls: they
never create, stop, or discard the recorder. Post-call policy work owns any
later redaction or deletion.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


async def handle_recording_consent_event(event, ctx):
    """Apply a caller's recording decision to the live session.

    The body lives here rather than in `sockets/websocket/handlers/` because it
    needs both layers — `SessionContext` from `modules/` and this module's gate
    — and `pipelines/` is the layer allowed to hold both. The socket handler is
    a one-line delegation, which also keeps the sockets → modules ratchet from
    growing by one import per new handler.
    """
    from fastapi import status

    from eylo.pipelines.websocket.handlers.error import handle_error
    from eylo.pipelines.websocket.schemas import WsEventAction, WsResponse

    try:
        if ctx.ws is None:
            return await handle_error(event, ctx)

        if bool((event.data or {}).get("granted", False)):
            grant(ctx.ws)
        else:
            await decline(ctx.ws)

        return WsResponse(
            status=status.HTTP_200_OK,
            kind=WsEventAction.RECORDING_CONSENT_STATE,
            data={
                "state": ctx.ws.recording_consent_state,
                "recording": ctx.ws.audio_recorder is not None,
                "_event": event.model_dump(),
            },
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            request_id=event.request_id,
        )
    except Exception as error:
        logger.error(
            "Recording consent handling failed error_type=%s",
            type(error).__name__,
        )
        return await handle_error(event, ctx)


def _label(session_state) -> str:
    """Identify the session in logs across both runtimes.

    Browser sessions carry `session_id`, telephony calls carry `call_sid`.
    Everything else here is identical between them, which is why the gate is
    shared rather than reimplemented per runtime.
    """
    return getattr(session_state, "session_id", None) or getattr(
        session_state, "call_sid", "unknown"
    )


def is_pending(session_state) -> bool:
    return session_state.recording_consent_state == "pending"


async def announce_and_grant(
    session_state,
    tts_manager,
    message: str,
    *,
    deliver: Callable[[str], Awaitable[bool]] | None = None,
) -> bool:
    """Speak the disclosure and record whether delivery was queued.

    The disclosure is spoken regardless of `first_message_mode`. It is not a
    greeting the operator chose to play — it is the thing that makes recording
    lawful, so an agent configured to wait for the caller still discloses.

    State becomes ``granted`` after the text is queued and flushed rather than
    after audio is confirmed heard, which is the limit of the TTS contract.
    Recording already runs independently of this notification.
    """
    if not is_pending(session_state):
        return False

    if tts_manager is None and deliver is None:
        logger.warning(
            "Recording consent for session %s stays pending: no TTS to deliver "
            "the disclosure. Recording continues as the primary voice flow.",
            _label(session_state),
        )
        return False

    turn_id = f"consent-{uuid4()}"
    try:
        if deliver is not None:
            delivered = await deliver(message)
            if not delivered:
                return False
        else:
            await tts_manager.add_to_request_queue(
                {"type": "text", "text": message, "turn_id": turn_id}
            )
            await tts_manager.add_to_request_queue(
                {"type": "finalize", "turn_id": turn_id}
            )
    except Exception as error:
        logger.error(
            "Recording consent for session %s stays pending: the disclosure "
            "could not be delivered. Recording continues as the primary voice "
            "flow. error_type=%s",
            _label(session_state),
            type(error).__name__,
        )
        return False

    return grant(session_state)


def grant(session_state) -> bool:
    """Move a pending notification to granted without gating recording."""
    if not is_pending(session_state):
        return False

    session_state.recording_consent_state = "granted"
    logger.info(
        "Recording notification delivered for session %s.",
        _label(session_state),
    )
    return True


async def decline(session_state) -> None:
    """Record caller feedback without interrupting the primary voice flow."""
    session_state.recording_consent_state = "declined"
    logger.info(
        "Recording notification declined for session %s; recording continues. "
        "The caller may end the call, and post-call policy may delete it.",
        _label(session_state),
    )
