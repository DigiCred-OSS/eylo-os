"""Agent-facing telephony tools gated by call and provider authority."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from eylo.common.contracts.telephony import CallEndedReason
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.call import (
    CallDirection,
    CallTransferringEvent,
)
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.telephony.lifecycle import (
    record_call_transfer_outcome,
    record_call_transfer_requested,
)
from eylo.modules.telephony.provider_config_domain import TelephonyOperation
from eylo.pipelines.telephony.call_control import VoiceService
from eylo.pipelines.telephony.sessions import S_CALLS, CallSession
from eylo.pipelines.telephony.voice import terminate_telephony_voice
from eylo.pipelines.voice.request_state import VoiceRequestSource

logger = logging.getLogger(__name__)


def _resolve_active_call(ctx: ConversationContext) -> Optional[CallSession]:
    """Resolve the active call session from the conversation context.

    Scans S_CALLS for a session matching the conversation's ID.

    Returns:
        The active CallSession, or None if no active call.

    """
    conversation = ctx.conversation
    matches = [
        session
        for session in S_CALLS.active_sessions()
        if session.conversation_id == conversation.id
        and session.organization_id == conversation.organization_id
        and session.is_active
    ]
    if len(matches) > 1:
        logger.error("Active carrier call authority was ambiguous.")
        return None
    return matches[0] if matches else None


_resolve_active_call.__eylo_hidden__ = True


def _resolve_provider(session: CallSession) -> str:
    """Return the provider already pinned on the active call session."""
    if not session.provider:
        raise ValueError("Active call is missing its telephony provider.")
    return session.provider


_resolve_provider.__eylo_hidden__ = True


def _require_session_authority(session: CallSession) -> tuple[UUID, UUID, int]:
    if (
        session.organization_id is None
        or session.provider_config_id is None
        or session.provider_config_revision is None
    ):
        raise ValueError("Active call is missing pinned telephony authority.")
    return (
        session.organization_id,
        session.provider_config_id,
        session.provider_config_revision,
    )


_require_session_authority.__eylo_hidden__ = True


def _build_call_event_kwargs(session: CallSession, provider: str) -> dict:
    """Build common kwargs for call events from a CallSession."""
    organization_id, provider_config_id, provider_config_revision = (
        _require_session_authority(session)
    )
    return {
        "call_sid": session.call_sid,
        "session_id": session.auth_session_token
        or session.stream_sid
        or session.call_sid,
        "organization_id": organization_id,
        "conversation_id": session.conversation_id,
        "direction": CallDirection(session.direction)
        if session.direction
        else CallDirection.INBOUND,
        "provider": provider,
        "provider_config_id": provider_config_id,
        "provider_config_revision": provider_config_revision,
        "from_number": session.from_number,
        "to_number": session.to_number,
        "agent_id": session.agent_id,
        "agent_revision": session.agent_revision,
    }


_build_call_event_kwargs.__eylo_hidden__ = True


def _transfer_failure_projection(error: Exception) -> tuple[str, str]:
    """Map a safe control error onto the durable transfer state machine."""
    detail = getattr(error, "detail", None)
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "UNKNOWN":
        return "unknown", "call_transfer_unconfirmed"
    return "failed", "call_transfer_rejected"


_transfer_failure_projection.__eylo_hidden__ = True


# ---------------------------------------------------------------------------
# end_call tool
# ---------------------------------------------------------------------------


async def end_call(ctx: ConversationContext, *args, **kwargs) -> str:
    """End the exact active voice session after delivering any final response.

    Use this after saying goodbye when the conversation is complete, the caller
    wants to hang up, or the Agent needs to terminate voice interaction. The
    platform routes live Agent execution to browser, realtime, or telephony
    teardown. This direct fallback resolves an active carrier call.

    No arguments needed.

    Args:
        ctx: Internal conversation context (injected automatically).

    Returns:
        JSON string with the result status.

    """
    call_sid: str | None = None
    try:
        session = _resolve_active_call(ctx)
        if not session:
            return '{"status": "error", "message": "No active call found for this conversation"}'

        call_sid = session.call_sid
        _require_session_authority(session)
        telephony_manager = session.telephony_manager
        if telephony_manager is None:
            raise RuntimeError("Active call has no transport manager.")

        accepted = await terminate_telephony_voice(
            sess=session,
            telephony_manager=telephony_manager,
            ended_reason=CallEndedReason.AGENT_ENDED_CALL,
            source=VoiceRequestSource.END_CALL,
        )
        if not accepted:
            return '{"status": "error", "message": "Call termination was not accepted."}'

        # Note: CallEndedEvent is emitted by media_stream.py cleanup (finally block)
        # when the WebSocket disconnects after end_call. We don't emit here to avoid
        # duplicate events. The ended_reason set above will be picked up by cleanup.

        return f'{{"status": "success", "message": "Call ended", "call_sid": "{call_sid}"}}'

    except Exception as error:
        logger.error(
            "end_call tool failed call_sid=%s error_type=%s",
            call_sid,
            type(error).__name__,
        )
        return '{"status": "error", "message": "Call could not be ended."}'


# ---------------------------------------------------------------------------
# transfer_call tool
# ---------------------------------------------------------------------------


async def transfer_call(
    to_number: str,
    ctx: ConversationContext,
    *args,
    **kwargs,
) -> str:
    """Transfer the current active phone call to another number.

    Use this when the caller needs to be connected to a different person,
    department, or external number. The agent's leg of the call will disconnect
    after the transfer is initiated.

    Args:
        to_number: The destination phone number in E.164 format (e.g., '+16054440129').
        ctx: Internal conversation context (injected automatically).

    Returns:
        JSON string with the result status.

    """
    call_sid = "unknown"
    session: CallSession | None = None
    transfer_intent_committed = False
    try:
        if not to_number or not re.match(r"^\+[1-9]\d{1,14}$", to_number):
            return '{"status": "error", "message": "Invalid to_number. Must be E.164 format (e.g., +16054440129)"}'

        session = _resolve_active_call(ctx)
        if not session:
            return '{"status": "error", "message": "No active call found for this conversation"}'

        call_sid = session.call_sid
        provider = _resolve_provider(session)
        organization_id, _, _ = _require_session_authority(session)
        voice_service = VoiceService()

        await voice_service.require_control_supported(
            call_sid=call_sid,
            organization_id=organization_id,
            operation=TelephonyOperation.TRANSFER_CALL,
        )

        transfer_event = CallTransferringEvent(
            message=f"Transferring call to {to_number}",
            transfer_to=to_number,
            **_build_call_event_kwargs(session, provider),
        )
        await record_call_transfer_requested(
            organization_id=transfer_event.organization_id,
            call_sid=transfer_event.call_sid,
            transfer_to=transfer_event.transfer_to,
            reason=transfer_event.data.get("transfer_reason"),
            metadata=transfer_event.data,
        )
        transfer_intent_committed = True
        try:
            emit_ephemeral(transfer_event)
        except Exception as emit_error:
            logger.error(
                "Could not emit local transfer delta call_sid=%s error_type=%s",
                transfer_event.call_sid,
                type(emit_error).__name__,
            )

        await voice_service.transfer_call(
            call_sid=call_sid,
            to_number=to_number,
            organization_id=organization_id,
        )
        try:
            await record_call_transfer_outcome(
                organization_id=organization_id,
                call_sid=call_sid,
                outcome="accepted",
            )
        except Exception as persistence_error:
            logger.error(
                "Could not persist accepted transfer outcome call_sid=%s error_type=%s",
                call_sid,
                type(persistence_error).__name__,
            )
        session.ended_reason = CallEndedReason.AGENT_FORWARDED_CALL
        session.extra_data["transfer_to"] = to_number

        return json.dumps(
            {
                "status": "success",
                "message": f"Call transferred to {to_number}",
                "call_sid": call_sid,
            }
        )

    except Exception as error:
        if transfer_intent_committed and session is not None:
            outcome, failure_code = _transfer_failure_projection(error)
            try:
                await record_call_transfer_outcome(
                    organization_id=organization_id,
                    call_sid=call_sid,
                    outcome=outcome,
                    failure_code=failure_code,
                )
            except Exception as persistence_error:
                logger.error(
                    "Could not persist transfer outcome outcome=%s call_sid=%s error_type=%s",
                    outcome,
                    call_sid,
                    type(persistence_error).__name__,
                )
        logger.error(
            "transfer_call tool failed call_sid=%s error_type=%s",
            call_sid,
            type(error).__name__,
        )
        return json.dumps(
            {
                "status": "error",
                "message": "Call transfer was not accepted.",
            }
        )


# ---------------------------------------------------------------------------
# dial_keypad tool
# ---------------------------------------------------------------------------


async def dial_keypad(
    digits: str,
    ctx: ConversationContext,
    *args,
    **kwargs,
) -> str:
    """Send DTMF tones (keypad digits) on the current active phone call.

    Use this only for non-sensitive IVR navigation. Payment authentication,
    PIN, CVV, OTP, and other secret entry are unsupported in V1.

    Args:
        digits: The DTMF digits to send. Valid characters: 0-9, *, #, w (0.5s pause).
                Example: '1234#' or '1w2w3' (with pauses).
        ctx: Internal conversation context (injected automatically).

    Returns:
        JSON string with the result status.

    """
    call_sid: str | None = None
    try:
        if not digits or not re.match(r"^[0-9*#wW]+$", digits):
            return '{"status": "error", "message": "Invalid digits. Use 0-9, *, #, or w (pause)."}'

        session = _resolve_active_call(ctx)
        if not session:
            return '{"status": "error", "message": "No active call found for this conversation"}'

        call_sid = session.call_sid
        organization_id, _, _ = _require_session_authority(session)
        voice_service = VoiceService()

        await voice_service.send_dtmf(
            call_sid=call_sid,
            digits=digits,
            organization_id=organization_id,
        )

        return json.dumps(
            {
                "status": "success",
                "message": "DTMF tones sent.",
                "call_sid": call_sid,
            }
        )

    except Exception as error:
        logger.error(
            "dial_keypad tool failed call_sid=%s error_type=%s",
            call_sid,
            type(error).__name__,
        )
        return json.dumps(
            {
                "status": "error",
                "message": "DTMF tones were not accepted.",
            }
        )


# ---------------------------------------------------------------------------
# schedule_call tool
# ---------------------------------------------------------------------------


async def schedule_call(
    to_number: str,
    initial_message: str,
    call_at: str,
    ctx: ConversationContext,
    meta: Optional[Dict[str, Any]] = None,
    *args,
    **kwargs,
) -> str:
    """Schedule a future outbound phone call.

    Use this to plan a call that should happen at a specific time. The system
    will automatically place the call at the scheduled time using the agent's
    configured phone number and telephony provider.

    Args:
        to_number: Destination phone number in E.164 format (e.g., '+919876543210').
        initial_message: The opening message the agent should speak when the
                         call connects. Keep it natural and conversational.
        call_at: UTC timestamp in ISO 8601 format (e.g., '2025-10-11T14:30:00Z').
                 Must be in the future.
        ctx: Internal conversation context (injected automatically).
        meta: Optional metadata dict for campaign or caller-specific context
              (e.g., {"campaign_id": "...", "contact_name": "John"}).

    Returns:
        JSON string with the scheduling result.

    """
    try:
        # Validate phone number
        if not to_number or not re.match(r"^\+[1-9]\d{1,14}$", to_number):
            return '{"status": "error", "message": "Invalid to_number. Must be E.164 format."}'

        # Validate call_at
        try:
            scheduled_time = datetime.fromisoformat(call_at.replace("Z", "+00:00"))
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return '{"status": "error", "message": "Invalid call_at format. Use ISO 8601 UTC."}'

        now = datetime.now(timezone.utc)
        if scheduled_time < now:
            return (
                '{"status": "error", "message": "Cannot schedule a call in the past."}'
            )

        # Resolve agent and org
        primary_agent = ctx.get_primary_agent()
        if not primary_agent:
            return '{"status": "error", "message": "No primary agent found in conversation context."}'

        agent_id = primary_agent.entity_id
        agent_revision = primary_agent.agent_revision
        org_id = ctx.conversation.organization_id
        if agent_revision is None:
            return (
                '{"status": "error", "message": "Primary agent has no exact revision."}'
            )

        # The old row carried a sender_participant_id it never used — the call
        # executor read `meta`, not the column. Dropped rather than carried
        # forward into a payload nothing reads.

        # Build schedule metadata — generic, no hardcoded use case
        schedule_meta: Dict[str, Any] = {
            "kind": "outbound_call",
            "to_number": to_number,
            "agent_id": str(agent_id),
            "org_id": str(org_id),
            "initial_message": initial_message,
            "call_at": call_at,
        }
        if meta:
            schedule_meta.update(meta)

        # Through the scheduler, as a one-shot. This used to write to
        # `tool_agent_schedules`, polled by a cron whose only recovery was an
        # in-memory lock and a status column set by hand. The occurrence now
        # has a lease, attempts and a run record.
        #
        # UTC, because `call_at` is an absolute instant with no wall-clock
        # intent to preserve. A recurring call campaign would need the
        # recipient's timezone, which is why this stays one-shot.
        from eylo.common.contracts.scheduler import Recurrence
        from eylo.modules.scheduler.service import create_schedule

        await create_schedule(
            organization_id=org_id,
            # Unique per call. Two calls to the same number are two calls, so a
            # stable key would have the second silently replace the first.
            key=f"call:{agent_id}:{uuid4()}",
            name=f"Outbound call to {to_number}",
            action="telephony.place_call",
            payload=schedule_meta,
            recurrence=Recurrence(rule=None, timezone="UTC", starts_at=scheduled_time),
            agent_id=agent_id,
            agent_revision=agent_revision,
        )

        logger.info("Call scheduled at=%s agent=%s", call_at, agent_id)
        return f'{{"status": "scheduled", "scheduled_time": "{call_at}", "to_number": "{to_number}"}}'

    except Exception as error:
        logger.error(
            "schedule_call tool failed error_type=%s",
            type(error).__name__,
        )
        return '{"status": "error", "message": "Call could not be scheduled."}'


# ---------------------------------------------------------------------------
# place_call tool
# ---------------------------------------------------------------------------


async def place_call(
    to_number: str,
    initial_message: str,
    ctx: ConversationContext,
    *args,
    **kwargs,
) -> str:
    """Immediately initiate an outbound phone call.

    Use this to place a call right now (no scheduling). The system will connect
    the call using the agent's configured phone number and telephony provider.

    Args:
        to_number: Destination phone number in E.164 format (e.g., '+919876543210').
        initial_message: The opening message the agent should speak when the
                         call connects.
        ctx: Internal conversation context (injected automatically).

    Returns:
        JSON string with the call initiation result.

    """
    del to_number, initial_message, ctx, args, kwargs
    return json.dumps(
        {
            "kind": "telephony_error",
            "error": "durable_execution_required",
        }
    )
