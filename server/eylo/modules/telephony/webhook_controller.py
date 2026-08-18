"""Webhook controller for telephony provider status callbacks.

Normalizes provider-specific status formats into unified call events
and updates the call persistence layer.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import arrow

from eylo.common.contracts.telephony import CallEndedReason
from eylo.common.database import start_transaction
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.call import (
    CallEndedEvent,
    CallRingingEvent,
)
from eylo.modules.telephony.lifecycle import record_call_status
from eylo.modules.telephony.schemas import CallStatus
from eylo.modules.telephony.services import TelephonyCallService
from eylo.pipelines.telephony.sessions import S_CALLS

logger = logging.getLogger(__name__)


def _status_value(status: str | CallStatus) -> str:
    return status.value if isinstance(status, CallStatus) else str(status)


# Twilio CallStatus -> our CallStatus mapping
TWILIO_STATUS_MAP: Dict[str, CallStatus] = {
    "queued": CallStatus.INITIATED,
    "ringing": CallStatus.RINGING,
    "in-progress": CallStatus.IN_PROGRESS,
    "completed": CallStatus.COMPLETED,
    "busy": CallStatus.BUSY,
    "no-answer": CallStatus.NO_ANSWER,
    "failed": CallStatus.FAILED,
    "canceled": CallStatus.CANCELED,
}

PLIVO_STATUS_MAP: Dict[str, CallStatus] = {
    "ring": CallStatus.RINGING,
    "answer": CallStatus.IN_PROGRESS,
    "hangup": CallStatus.COMPLETED,
    "busy": CallStatus.BUSY,
    "timeout": CallStatus.NO_ANSWER,
    "cancel": CallStatus.CANCELED,
    "machine": CallStatus.COMPLETED,
}

VONAGE_STATUS_MAP: Dict[str, CallStatus] = {
    "started": CallStatus.INITIATED,
    "ringing": CallStatus.RINGING,
    "answered": CallStatus.IN_PROGRESS,
    "completed": CallStatus.COMPLETED,
    "busy": CallStatus.BUSY,
    "timeout": CallStatus.NO_ANSWER,
    "failed": CallStatus.FAILED,
    "rejected": CallStatus.FAILED,
    "cancelled": CallStatus.CANCELED,
    "unanswered": CallStatus.NO_ANSWER,
}

EXOTEL_STATUS_MAP: Dict[str, CallStatus] = {
    "in-progress": CallStatus.IN_PROGRESS,
    "completed": CallStatus.COMPLETED,
    "failed": CallStatus.FAILED,
    "busy": CallStatus.BUSY,
    "no-answer": CallStatus.NO_ANSWER,
}

TERMINAL_CALL_STATUSES = (
    CallStatus.COMPLETED,
    CallStatus.BUSY,
    CallStatus.NO_ANSWER,
    CallStatus.FAILED,
    CallStatus.CANCELED,
)

STATUS_TO_ENDED_REASON: Dict[CallStatus, CallEndedReason] = {
    CallStatus.BUSY: CallEndedReason.CUSTOMER_BUSY,
    CallStatus.NO_ANSWER: CallEndedReason.CUSTOMER_DID_NOT_ANSWER,
    CallStatus.FAILED: CallEndedReason.ERROR_PROVIDER_DISCONNECTED,
    CallStatus.CANCELED: CallEndedReason.MANUALLY_CANCELED,
}


class WebhookController:
    """Handles provider status webhooks and updates call records."""

    async def _handle_provider_status(
        self,
        payload: Dict[str, Any],
        provider: str,
        call_sid_field: str,
        status_field: str,
        status_map: Dict[str, CallStatus],
        duration_field: str,
    ) -> None:
        """Normalize a provider callback payload and update the call record."""
        call_sid = str(payload.get(call_sid_field, ""))
        raw_status = str(payload.get(status_field, ""))
        status = status_map.get(raw_status)
        duration = payload.get(duration_field)

        if not call_sid or not status:
            logger.warning(
                "[%s] Invalid webhook: sid=%s status=%s",
                provider,
                call_sid,
                raw_status,
            )
            return

        logger.info("[%s] Status callback: %s → %s", provider, call_sid, raw_status)
        await self._update_call_status(
            call_sid=call_sid,
            status=status,
            provider=provider,
            provider_status=raw_status,
            duration_seconds=int(duration) if duration else None,
        )

    async def _update_call_status(
        self,
        call_sid: str,
        status: str,
        provider: str,
        provider_status: Optional[str] = None,
        ended_reason: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Update call record from webhook status.

        Raises on DB failure so the route can return 5xx for provider retry.
        Retries briefly when the call is active in memory but not yet persisted
        (race between webhook and CallStartedEvent DB insert).
        """
        call = None
        # Retry loop: webhook can arrive before persist_call_started inserts the row
        for attempt in range(3):
            async with start_transaction():
                svc = TelephonyCallService()
                call = await svc.get_by_call_sid(call_sid)
            if call:
                break
            # Only retry if the call is active in memory (race), not truly unknown
            if not S_CALLS.find_by_provider_call(provider, call_sid):
                logger.debug(
                    f"[{provider}] Call {call_sid} not in DB or memory, skipping"
                )
                return
            logger.debug(
                f"[{provider}] Call {call_sid} active but not in DB yet, "
                f"retry {attempt + 1}/3"
            )
            await asyncio.sleep(0.3 * (attempt + 1))

        if not call:
            logger.warning(
                f"[{provider}] Call {call_sid} not in DB after retries, skipping"
            )
            return
        if call.provider != provider:
            raise ValueError("Call provider does not match callback provider.")

        is_terminal = status in TERMINAL_CALL_STATUSES
        update_kwargs: Dict[str, Any] = {
            "call_sid": call_sid,
            "status": status,
            "provider_status": provider_status,
        }
        if is_terminal:
            update_kwargs["ended_at"] = arrow.utcnow().datetime
            if duration_seconds is not None:
                update_kwargs["duration_seconds"] = duration_seconds
            if ended_reason:
                update_kwargs["ended_reason"] = ended_reason
            elif status in STATUS_TO_ENDED_REASON:
                update_kwargs["ended_reason"] = STATUS_TO_ENDED_REASON[status]

        lifecycle_result = await record_call_status(
            organization_id=call.organization_id,
            source="provider_callback",
            **update_kwargs,
        )
        update_result = lifecycle_result.update
        updated_call = update_result.call
        if updated_call and _status_value(updated_call.status) != _status_value(status):
            logger.info(
                "[%s] Ignored stale call status event for %s: incoming=%s persisted=%s",
                provider,
                call_sid,
                status,
                updated_call.status,
            )
            return
        if not updated_call:
            return
        if update_result.ignored:
            logger.info(
                "[%s] Ignored duplicate call status event for %s: incoming=%s persisted=%s",
                provider,
                call_sid,
                status,
                updated_call.status,
            )
            return
        logger.info("[%s] Updated call %s → %s", provider, call_sid, status)

        # Resolve WS-routable session_id: prefer live session, fall back to DB id
        call_for_event = updated_call
        session_id = S_CALLS.resolve_session_id(
            provider,
            call_sid,
            call_for_event.organization_id,
        ) or str(call_for_event.id)

        # Emit ringing event for outbound calls
        if (
            status == CallStatus.RINGING
            and update_result.status_changed
            and call_for_event.organization_id
        ):
            emit_ephemeral(
                CallRingingEvent(
                    message=f"Call ringing ({provider})",
                    session_id=session_id,
                    organization_id=call_for_event.organization_id,
                    call_sid=call_sid,
                    conversation_id=call_for_event.conversation_id,
                    provider=provider,
                    provider_config_id=call_for_event.provider_config_id,
                    provider_config_revision=(call_for_event.provider_config_revision),
                    from_number=call_for_event.from_number,
                    to_number=call_for_event.to_number,
                    agent_id=call_for_event.agent_id,
                    agent_revision=call_for_event.agent_revision,
                ),
            )

        # Emit ended event only for the first transition into a terminal status.
        if (
            is_terminal
            and update_result.entered_terminal_status
            and call_for_event.organization_id
        ):
            reason = ended_reason or STATUS_TO_ENDED_REASON.get(
                status, CallEndedReason.UNKNOWN
            )
            emit_ephemeral(
                CallEndedEvent(
                    message=f"Call ended ({provider}): {reason}",
                    session_id=session_id,
                    organization_id=call_for_event.organization_id,
                    call_sid=call_sid,
                    conversation_id=call_for_event.conversation_id,
                    provider=provider,
                    provider_config_id=call_for_event.provider_config_id,
                    provider_config_revision=(call_for_event.provider_config_revision),
                    from_number=call_for_event.from_number,
                    to_number=call_for_event.to_number,
                    agent_id=call_for_event.agent_id,
                    agent_revision=call_for_event.agent_revision,
                    ended_reason=reason,
                    duration_seconds=duration_seconds,
                    terminal_status=status,
                    data={
                        "campaign_id": call_for_event.campaign_id,
                        "campaign_contact_id": (call_for_event.campaign_contact_id),
                        "campaign_attempt_id": call_for_event.campaign_attempt_id,
                    }
                    if call_for_event.campaign_id
                    else {},
                ),
            )

    async def handle_twilio_status(self, form: Dict[str, Any]) -> None:
        """Handle Twilio status callback.

        Twilio sends: CallSid, CallStatus, CallDuration (on completed)
        """
        await self._handle_provider_status(
            payload=form,
            provider="twilio",
            call_sid_field="CallSid",
            status_field="CallStatus",
            status_map=TWILIO_STATUS_MAP,
            duration_field="CallDuration",
        )

    async def handle_plivo_status(self, form: Dict[str, Any]) -> None:
        """Handle Plivo status callback.

        Plivo sends: CallUUID, CallStatus, Duration (on hangup)
        """
        await self._handle_provider_status(
            payload=form,
            provider="plivo",
            call_sid_field="CallUUID",
            status_field="CallStatus",
            status_map=PLIVO_STATUS_MAP,
            duration_field="Duration",
        )

    async def handle_vonage_status(self, body: Dict[str, Any]) -> None:
        """Handle Vonage event callback.

        Vonage sends JSON: uuid, status, duration (on completed)
        """
        await self._handle_provider_status(
            payload=body,
            provider="vonage",
            call_sid_field="uuid",
            status_field="status",
            status_map=VONAGE_STATUS_MAP,
            duration_field="duration",
        )

    async def handle_exotel_status(self, form: Dict[str, Any]) -> None:
        """Handle Exotel status callback.

        Exotel sends: CallSid, Status, Duration
        """
        await self._handle_provider_status(
            payload=form,
            provider="exotel",
            call_sid_field="CallSid",
            status_field="Status",
            status_map=EXOTEL_STATUS_MAP,
            duration_field="Duration",
        )
