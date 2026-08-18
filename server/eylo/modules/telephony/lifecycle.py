"""Authoritative organization-scoped telephony call lifecycle commands."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.common.outbound import OutboundAttemptState, require_failure_code
from eylo.events.durable.binding import spawn_event_deliveries
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventService
from eylo.modules.telephony.repositories import TelephonyCallRepository
from eylo.modules.telephony.schemas import (
    CallStatus,
    TelephonyCallInDb,
    TelephonyCallStatusUpdateResult,
)
from eylo.modules.telephony.services import TelephonyCallService
from eylo.modules.user_sessions.events import file_user_session_fact

logger = logging.getLogger(__name__)

CALL_ENDED_EVENT_TYPE = "telephony.call.ended"
CALL_ENDED_EVENT_VERSION = 1
CALL_SUBJECT_TYPE = "telephony.call"
CAMPAIGN_CALL_OUTCOME_CONSUMER = "campaign.call_outcome"

_TERMINAL_STATUSES = frozenset(
    {
        CallStatus.COMPLETED.value,
        CallStatus.BUSY.value,
        CallStatus.NO_ANSWER.value,
        CallStatus.FAILED.value,
        CallStatus.CANCELED.value,
    }
)


def is_terminal_call_status(status: str | CallStatus) -> bool:
    """Return whether a canonical call status ends the call lifecycle."""
    value = status.value if isinstance(status, CallStatus) else str(status)
    return value in _TERMINAL_STATUSES


class CallLifecycleNotFound(Exception):
    """The organization cannot resolve the requested active call authority."""


class CallLifecycleConflict(Exception):
    """A stable provider call identity conflicts with canonical call authority."""


class CallTransferNotSendable(CallLifecycleConflict):
    """A prior transfer intent prevents another provider transfer send."""


class CallMediaNotSendable(CallLifecycleConflict):
    """The outbound call cannot publish another realtime media session."""


@dataclass(frozen=True, slots=True)
class CallLifecycleStatusResult:
    """Canonical status result plus any terminal durable fact identity."""

    update: TelephonyCallStatusUpdateResult
    terminal_event_id: UUID | None


async def prepare_outbound_call(
    *,
    call_id: UUID,
    organization_id: UUID,
    provider: str,
    provider_config_id: UUID,
    provider_config_revision: int,
    from_number: str,
    to_number: str,
    phone_number_id: UUID,
    agent_id: UUID,
    agent_revision: int,
    conversation_id: UUID | None = None,
    campaign_id: UUID | None = None,
    campaign_contact_id: UUID | None = None,
    campaign_attempt_id: UUID | None = None,
) -> TelephonyCallInDb:
    """Commit one stable call intent before any carrier can charge or callback."""
    async with start_transaction() as session:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": f"telephony-call-intent:{organization_id}:{call_id}"},
        )
        repository = TelephonyCallRepository(session)
        existing = await repository.get_by_id_for_update(call_id, organization_id)
        expected = {
            "provider": provider,
            "provider_config_id": provider_config_id,
            "provider_config_revision": provider_config_revision,
            "direction": "outbound",
            "from_number": from_number,
            "to_number": to_number,
            "phone_number_id": phone_number_id,
            "agent_id": agent_id,
            "agent_revision": agent_revision,
            "conversation_id": conversation_id,
            "campaign_id": campaign_id,
            "campaign_contact_id": campaign_contact_id,
            "campaign_attempt_id": campaign_attempt_id,
        }
        if existing is not None:
            for field, value in expected.items():
                if getattr(existing, field) != value:
                    raise CallLifecycleConflict(
                        f"Call intent conflicts on canonical {field}."
                    )
            return TelephonyCallService(session).orm_to_schema(existing)
        return await TelephonyCallService(session).create_call(
            call_id=call_id,
            organization_id=organization_id,
            call_sid=None,
            **expected,
        )


async def apply_outbound_call_outcome(
    *,
    call_id: UUID,
    organization_id: UUID,
    state: OutboundAttemptState,
    provider_reference: str | None,
    failure_code: str | None,
) -> CallLifecycleStatusResult:
    """Project one charged-effect result onto its pre-existing call intent."""
    terminal_event_id: UUID | None = None
    async with start_transaction() as session:
        repository = TelephonyCallRepository(session)
        call = await repository.get_by_id_for_update(call_id, organization_id)
        if call is None:
            raise CallLifecycleNotFound
        provider_was_bound = provider_reference is not None and (
            call.call_sid == provider_reference
        )
        if provider_reference is not None:
            bound = await repository.get_by_call_sid_for_update(provider_reference)
            if bound is not None and bound.id != call.id:
                raise CallLifecycleConflict(
                    "Provider call identity is already bound to another call."
                )
            if call.call_sid not in {None, provider_reference}:
                raise CallLifecycleConflict(
                    "Call intent is already bound to another provider identity."
                )
            call.call_sid = provider_reference

        if _outbound_outcome_already_projected(
            call=call,
            state=state,
            failure_code=failure_code,
            provider_was_bound=provider_was_bound,
        ):
            result = TelephonyCallStatusUpdateResult(
                call=TelephonyCallService(session).orm_to_schema(call),
                incoming_status=call.status,
                ignored=True,
            )
            return CallLifecycleStatusResult(
                update=result,
                terminal_event_id=None,
            )

        observed_at = datetime.now(timezone.utc)
        history_entry = {
            "effect_state": state.value,
            "observed_at": observed_at.isoformat(),
        }
        call.status_history = [*(call.status_history or []), history_entry]
        if state is OutboundAttemptState.SUCCEEDED:
            if call.status not in _TERMINAL_STATUSES:
                call.provider_status = "accepted"
        elif state is OutboundAttemptState.RETRYABLE:
            call.provider_status = "retryable"
        elif state is OutboundAttemptState.UNKNOWN:
            call.provider_status = "initiation-unknown"
        elif state is OutboundAttemptState.TERMINAL:
            call.status = CallStatus.FAILED.value
            call.provider_status = "rejected"
            call.ended_reason = failure_code or "provider_rejected"
            call.ended_at = call.ended_at or observed_at
            fact = _terminal_envelope(TelephonyCallService(session).orm_to_schema(call))
            consumers = (
                (CAMPAIGN_CALL_OUTCOME_CONSUMER,)
                if call.campaign_attempt_id is not None
                else ()
            )
            await DurableEventService(session).file(
                envelope=fact,
                consumer_names=consumers,
            )
            terminal_event_id = fact.event_id
        else:
            raise ValueError(f"Unsupported outbound call outcome: {state.value}.")
        await session.flush()
        result = TelephonyCallStatusUpdateResult(
            call=TelephonyCallService(session).orm_to_schema(call),
            incoming_status=call.status,
            status_changed=state is OutboundAttemptState.TERMINAL,
            entered_terminal_status=state is OutboundAttemptState.TERMINAL,
        )

    if terminal_event_id is not None:
        await _nudge_terminal_fact(
            organization_id=organization_id,
            event_id=terminal_event_id,
        )
    return CallLifecycleStatusResult(
        update=result,
        terminal_event_id=terminal_event_id,
    )


def _outbound_outcome_already_projected(
    *,
    call: Any,
    state: OutboundAttemptState,
    failure_code: str | None,
    provider_was_bound: bool,
) -> bool:
    if state is OutboundAttemptState.SUCCEEDED:
        return provider_was_bound and call.provider_status is not None
    if state is OutboundAttemptState.RETRYABLE:
        return call.provider_status == "retryable"
    if state is OutboundAttemptState.UNKNOWN:
        return call.provider_status == "initiation-unknown"
    if state is OutboundAttemptState.TERMINAL:
        return call.status == CallStatus.FAILED.value and call.ended_reason == (
            failure_code or "provider_rejected"
        )
    return False


async def bind_outbound_provider_call(
    *,
    call_id: UUID,
    organization_id: UUID,
    provider_reference: str,
) -> TelephonyCallInDb:
    """Bind a callback identity even when it beats the initiating response."""
    result = await apply_outbound_call_outcome(
        call_id=call_id,
        organization_id=organization_id,
        state=OutboundAttemptState.SUCCEEDED,
        provider_reference=provider_reference,
        failure_code=None,
    )
    if result.update.call is None:
        raise CallLifecycleNotFound
    return result.update.call


async def claim_outbound_media_session(
    *,
    call_id: UUID,
    organization_id: UUID,
    provider: str,
    provider_call_sid: str,
    provider_config_id: UUID,
    provider_config_revision: int,
    agent_id: UUID,
    agent_revision: int,
    initial_message: str | None,
) -> TelephonyCallInDb:
    """Atomically bind and consume one signed outbound media-stream claim."""
    if not provider_call_sid.strip():
        raise CallMediaNotSendable("Provider call identity is required.")

    async with start_transaction() as session:
        repository = TelephonyCallRepository(session)
        call = await repository.get_by_id_for_update(call_id, organization_id)
        if call is None:
            raise CallLifecycleNotFound
        expected = {
            "provider": provider,
            "provider_config_id": provider_config_id,
            "provider_config_revision": provider_config_revision,
            "agent_id": agent_id,
            "agent_revision": agent_revision,
            "direction": "outbound",
        }
        for field, value in expected.items():
            if getattr(call, field) != value:
                raise CallMediaNotSendable(
                    f"Media claim conflicts on canonical {field}."
                )
        if call.status in _TERMINAL_STATUSES:
            raise CallMediaNotSendable("Terminal calls cannot open media sessions.")
        if call.media_claimed_at is not None:
            raise CallMediaNotSendable("Media stream claim was already consumed.")

        bound = await repository.get_by_call_sid_for_update(provider_call_sid)
        if bound is not None and bound.id != call.id:
            raise CallMediaNotSendable(
                "Provider call identity belongs to another call."
            )
        if call.call_sid not in {None, provider_call_sid}:
            raise CallMediaNotSendable(
                "Call is already bound to another provider identity."
            )

        observed_at = datetime.now(timezone.utc)
        call.call_sid = provider_call_sid
        call.media_claimed_at = observed_at
        call.opener_delivery_status = "pending" if initial_message else "not_requested"
        call.status_history = [
            *(call.status_history or []),
            {
                "media_claim": "consumed",
                "observed_at": observed_at.isoformat(),
            },
        ]
        await session.flush()
        return TelephonyCallService(session).orm_to_schema(call)


async def record_opener_delivery(
    *,
    call_id: UUID,
    organization_id: UUID,
    accepted: bool,
    db: AsyncSession | None = None,
) -> TelephonyCallInDb:
    """Persist the final carrier-facing delivery state of an outbound opener."""
    if db is not None:
        return await _record_opener_delivery(
            db=db,
            call_id=call_id,
            organization_id=organization_id,
            accepted=accepted,
        )
    async with start_transaction() as session:
        return await _record_opener_delivery(
            db=session,
            call_id=call_id,
            organization_id=organization_id,
            accepted=accepted,
        )


async def _record_opener_delivery(
    *,
    db: AsyncSession,
    call_id: UUID,
    organization_id: UUID,
    accepted: bool,
) -> TelephonyCallInDb:
    repository = TelephonyCallRepository(db)
    call = await repository.get_by_id_for_update(call_id, organization_id)
    if call is None:
        raise CallLifecycleNotFound
    target = "accepted" if accepted else "failed"
    if call.opener_delivery_status == target:
        return TelephonyCallService(db).orm_to_schema(call)
    if call.opener_delivery_status != "pending":
        raise CallLifecycleConflict(
            "Call does not have a pending outbound opener delivery."
        )
    observed_at = datetime.now(timezone.utc)
    call.opener_delivery_status = target
    if accepted:
        call.opener_delivered_at = observed_at
    call.status_history = [
        *(call.status_history or []),
        {
            "opener_delivery": target,
            "observed_at": observed_at.isoformat(),
        },
    ]
    await db.flush()
    return TelephonyCallService(db).orm_to_schema(call)


async def link_call_voice_session(
    *,
    call_id: UUID,
    organization_id: UUID,
    voice_session_id: UUID,
    db: AsyncSession | None = None,
) -> TelephonyCallInDb:
    """Link the canonical call to the voice timeline created for its media."""
    if db is not None:
        return await _link_call_voice_session(
            db=db,
            call_id=call_id,
            organization_id=organization_id,
            voice_session_id=voice_session_id,
        )
    async with start_transaction() as session:
        return await _link_call_voice_session(
            db=session,
            call_id=call_id,
            organization_id=organization_id,
            voice_session_id=voice_session_id,
        )


async def _link_call_voice_session(
    *,
    db: AsyncSession,
    call_id: UUID,
    organization_id: UUID,
    voice_session_id: UUID,
) -> TelephonyCallInDb:
    repository = TelephonyCallRepository(db)
    call = await repository.get_by_id_for_update(call_id, organization_id)
    if call is None:
        raise CallLifecycleNotFound
    if call.voice_session_id not in {None, voice_session_id}:
        raise CallLifecycleConflict("Call is linked to another voice session.")
    call.voice_session_id = voice_session_id
    await db.flush()
    return TelephonyCallService(db).orm_to_schema(call)


async def record_call_started(
    *,
    organization_id: UUID,
    call_sid: str,
    provider: str,
    provider_config_id: UUID,
    provider_config_revision: int,
    direction: str,
    from_number: str | None = None,
    to_number: str | None = None,
    agent_id: UUID | None = None,
    agent_revision: int | None = None,
    conversation_id: UUID | None = None,
    user_session_id: UUID | None = None,
    campaign_id: UUID | None = None,
    campaign_contact_id: UUID | None = None,
    campaign_attempt_id: UUID | None = None,
) -> TelephonyCallInDb:
    """Create one call row before any local started broadcast."""
    async with start_transaction() as session:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": f"telephony-call:{organization_id}:{call_sid}"},
        )
        repository = TelephonyCallRepository(session)
        existing = await repository.get_by_call_sid_for_update(call_sid)
        if existing is not None:
            if existing.organization_id != organization_id:
                raise CallLifecycleNotFound
            _validate_existing_call(
                existing=existing,
                provider=provider,
                provider_config_id=provider_config_id,
                provider_config_revision=provider_config_revision,
                direction=direction,
                agent_id=agent_id,
                agent_revision=agent_revision,
            )
            if conversation_id is not None:
                if existing.conversation_id not in {None, conversation_id}:
                    raise CallLifecycleConflict(
                        "Call is already linked to another conversation."
                    )
                existing.conversation_id = conversation_id
            if user_session_id is not None:
                if existing.user_session_id not in {None, user_session_id}:
                    raise CallLifecycleConflict(
                        "Call is already linked to another user session."
                    )
                existing.user_session_id = user_session_id
            await session.flush()
            call = TelephonyCallService(session).orm_to_schema(existing)
        else:
            call = await TelephonyCallService(session).create_call(
                organization_id=organization_id,
                call_sid=call_sid,
                provider=provider,
                provider_config_id=provider_config_id,
                provider_config_revision=provider_config_revision,
                direction=direction,
                from_number=from_number,
                to_number=to_number,
                agent_id=agent_id,
                agent_revision=agent_revision,
                conversation_id=conversation_id,
                user_session_id=user_session_id,
                campaign_id=campaign_id,
                campaign_contact_id=campaign_contact_id,
                campaign_attempt_id=campaign_attempt_id,
            )
        if call.user_session_id is not None:
            await file_user_session_fact(
                session,
                organization_id=call.organization_id,
                user_session_id=call.user_session_id,
                subject_type=CALL_SUBJECT_TYPE,
                subject_id=call.id,
                event_type="telephony.call.started",
                occurred_at=call.started_at,
                event_id=uuid5(
                    NAMESPACE_URL,
                    f"eylo:telephony.call.started:v1:{call.organization_id}:{call.id}",
                ),
                payload={
                    "conversation_id": (
                        str(call.conversation_id) if call.conversation_id else None
                    ),
                    "direction": call.direction,
                    "provider": call.provider,
                    "agent_id": str(call.agent_id) if call.agent_id else None,
                    "agent_revision": call.agent_revision,
                },
            )
        return call


async def record_call_status(
    *,
    organization_id: UUID,
    call_sid: str,
    status: str,
    provider_status: str | None = None,
    ended_reason: str | None = None,
    ended_at: datetime | None = None,
    connected_at: datetime | None = None,
    duration_seconds: int | None = None,
    conversation_id: UUID | None = None,
    source: str = "runtime",
) -> CallLifecycleStatusResult:
    """Commit one monotonic status transition and terminal fact atomically."""
    status_value = status.value if isinstance(status, CallStatus) else str(status)
    terminal = is_terminal_call_status(status_value)
    if terminal and ended_at is None:
        ended_at = datetime.now(timezone.utc)

    terminal_event_id: UUID | None = None
    async with start_transaction() as session:
        update = await TelephonyCallService(session).update_status_with_result(
            call_sid=call_sid,
            organization_id=organization_id,
            status=status_value,
            provider_status=provider_status,
            ended_reason=ended_reason,
            ended_at=ended_at,
            connected_at=connected_at,
            duration_seconds=duration_seconds,
            conversation_id=conversation_id,
            source=source,
        )
        call = update.call
        if call is None:
            raise CallLifecycleNotFound
        if update.entered_terminal_status:
            fact = _terminal_envelope(call)
            consumers = (
                (CAMPAIGN_CALL_OUTCOME_CONSUMER,)
                if call.campaign_attempt_id is not None
                else ()
            )
            await DurableEventService(session).file(
                envelope=fact,
                consumer_names=consumers,
            )
            terminal_event_id = fact.event_id
        elif update.status_changed and call.user_session_id is not None:
            event_type = {
                CallStatus.RINGING.value: "telephony.call.ringing",
                CallStatus.IN_PROGRESS.value: "telephony.call.answered",
            }.get(status_value, "telephony.call.status_changed")
            await file_user_session_fact(
                session,
                organization_id=call.organization_id,
                user_session_id=call.user_session_id,
                subject_type=CALL_SUBJECT_TYPE,
                subject_id=call.id,
                event_type=event_type,
                payload={
                    "conversation_id": (
                        str(call.conversation_id) if call.conversation_id else None
                    ),
                    "status": status_value,
                    "provider": call.provider,
                },
            )
        elif terminal and is_terminal_call_status(call.status):
            # Duplicate terminal observations are no-ops, but callers still
            # receive the one deterministic fact identity already committed.
            terminal_event_id = _terminal_envelope(call).event_id

    if terminal_event_id is not None and update.entered_terminal_status:
        await _nudge_terminal_fact(
            organization_id=organization_id,
            event_id=terminal_event_id,
        )
    return CallLifecycleStatusResult(
        update=update,
        terminal_event_id=terminal_event_id,
    )


async def record_call_transfer_requested(
    *,
    organization_id: UUID,
    call_sid: str,
    transfer_to: str,
    reason: str | None,
    metadata: dict[str, Any],
) -> TelephonyCallInDb:
    """Commit transfer intent before its local UI delta."""
    async with start_transaction() as session:
        call = await TelephonyCallRepository(session).get_by_call_sid_for_update(
            call_sid,
            organization_id,
        )
        if call is None:
            raise CallLifecycleNotFound
        if call.transfer_status in {
            "transferring",
            "accepted",
            "unknown",
            "transferred",
        }:
            raise CallTransferNotSendable(
                f"Transfer cannot begin from {call.transfer_status}."
            )
        call.transfer_status = "transferring"
        call.transfer_to = transfer_to
        call.transfer_reason = reason
        call.transfer_metadata = {
            **(call.transfer_metadata or {}),
            **metadata,
        }
        await session.flush()
        return TelephonyCallService(session).orm_to_schema(call)


async def record_call_transfer_outcome(
    *,
    organization_id: UUID,
    call_sid: str,
    outcome: str,
    failure_code: str | None = None,
) -> TelephonyCallInDb:
    """Project the typed carrier result without treating intent as success."""
    if outcome not in {"accepted", "failed", "unknown"}:
        raise ValueError("Invalid call transfer outcome.")
    if outcome == "accepted" and failure_code is not None:
        raise ValueError("Accepted transfer cannot have a failure code.")
    if outcome != "accepted" and not failure_code:
        raise ValueError("Failed/unknown transfer requires a failure code.")
    if failure_code is not None:
        failure_code = require_failure_code(failure_code)

    async with start_transaction() as session:
        call = await TelephonyCallRepository(session).get_by_call_sid_for_update(
            call_sid,
            organization_id,
        )
        if call is None:
            raise CallLifecycleNotFound
        if call.transfer_status == outcome:
            return TelephonyCallService(session).orm_to_schema(call)
        if call.transfer_status != "transferring":
            raise CallTransferNotSendable(
                f"Transfer outcome cannot apply from {call.transfer_status}."
            )
        call.transfer_status = outcome
        metadata = dict(call.transfer_metadata or {})
        metadata["carrier_outcome_at"] = datetime.now(timezone.utc).isoformat()
        if failure_code is not None:
            metadata["failure_code"] = failure_code
        call.transfer_metadata = metadata
        await session.flush()
        return TelephonyCallService(session).orm_to_schema(call)


async def record_call_transfer_completed(
    *,
    organization_id: UUID,
    call_sid: str,
    transfer_to: str | None,
    metadata: dict[str, Any],
) -> TelephonyCallInDb:
    """Commit transfer completion before its local UI delta."""
    async with start_transaction() as session:
        call = await TelephonyCallRepository(session).get_by_call_sid_for_update(
            call_sid,
            organization_id,
        )
        if call is None:
            raise CallLifecycleNotFound
        if call.transfer_status == "transferred":
            return TelephonyCallService(session).orm_to_schema(call)
        if call.transfer_status != "accepted":
            raise CallTransferNotSendable(
                f"Transfer completion cannot apply from {call.transfer_status}."
            )
        call.transfer_status = "transferred"
        call.transfer_to = transfer_to or call.transfer_to
        call.transferred_at = datetime.now(timezone.utc)
        call.transfer_metadata = {
            **(call.transfer_metadata or {}),
            **metadata,
        }
        await session.flush()
        result = TelephonyCallService(session).orm_to_schema(call)
        if result.user_session_id is not None:
            await file_user_session_fact(
                session,
                organization_id=result.organization_id,
                user_session_id=result.user_session_id,
                subject_type=CALL_SUBJECT_TYPE,
                subject_id=result.id,
                event_type="telephony.call.transferred",
                occurred_at=result.transferred_at,
                payload={
                    "conversation_id": (
                        str(result.conversation_id) if result.conversation_id else None
                    ),
                    "provider": result.provider,
                },
            )
        return result


async def _nudge_terminal_fact(*, organization_id: UUID, event_id: UUID) -> None:
    try:
        result = await spawn_event_deliveries(
            organization_id=organization_id,
            event_id=event_id,
        )
    except Exception as error:  # noqa: BLE001 - DB recovery owns eventual spawn
        logger.error(
            "Could not nudge terminal call fact event=%s error_type=%s",
            event_id,
            type(error).__name__,
        )
        return
    for delivery_id, _summary in result.failures:
        logger.error(
            "Could not nudge terminal call delivery id=%s",
            delivery_id,
        )


def _terminal_envelope(call: TelephonyCallInDb) -> DurableEventEnvelope:
    if call.ended_at is None:
        raise CallLifecycleConflict("Terminal call is missing ended_at.")
    observed_at = datetime.now(timezone.utc)
    if call.ended_at > observed_at:
        raise CallLifecycleConflict("Terminal call ended_at is in the future.")
    return DurableEventEnvelope(
        event_id=uuid5(
            NAMESPACE_URL,
            f"eylo:{CALL_ENDED_EVENT_TYPE}:v1:{call.organization_id}:{call.id}",
        ),
        organization_id=call.organization_id,
        subject_type=CALL_SUBJECT_TYPE,
        subject_id=call.id,
        event_type=CALL_ENDED_EVENT_TYPE,
        event_version=CALL_ENDED_EVENT_VERSION,
        occurred_at=call.ended_at,
        recorded_at=call.ended_at,
        correlation_id=call.user_session_id,
        payload={
            "conversation_id": str(call.conversation_id),
            "status": call.status,
            "reason": call.ended_reason,
            "duration_seconds": call.duration_seconds,
        },
    )


def _validate_existing_call(
    *,
    existing: Any,
    provider: str,
    provider_config_id: UUID,
    provider_config_revision: int,
    direction: str,
    agent_id: UUID | None,
    agent_revision: int | None,
) -> None:
    expected = {
        "provider": provider,
        "provider_config_id": provider_config_id,
        "provider_config_revision": provider_config_revision,
        "direction": direction,
    }
    for field, value in expected.items():
        if getattr(existing, field) != value:
            raise CallLifecycleConflict(
                f"Call identity conflicts on canonical {field}."
            )
    if agent_id is not None and existing.agent_id not in {None, agent_id}:
        raise CallLifecycleConflict("Call identity conflicts on canonical agent_id.")
    if agent_revision is not None and existing.agent_revision not in {
        None,
        agent_revision,
    }:
        raise CallLifecycleConflict(
            "Call identity conflicts on canonical agent_revision."
        )
