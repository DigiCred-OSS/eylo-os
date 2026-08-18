"""Authoritative durable completion command for canonical voice sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.events.durable.binding import spawn_event_deliveries
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventService
from eylo.events.durable.voice_contracts import (
    VOICE_SESSION_COMPLETION_CONSUMER,
    VOICE_SESSION_ENDED_EVENT_TYPE,
    VOICE_SESSION_ENDED_EVENT_VERSION,
    VOICE_SESSION_SUBJECT_TYPE,
)
from eylo.modules.voice_transcripts.constants import (
    VoiceRuntimeMode,
    VoiceSessionStatus,
)
from eylo.modules.voice_transcripts.models import VoiceSessionModel

logger = logging.getLogger(__name__)


class VoiceSessionAuthorityMissing(Exception):
    """The organization cannot resolve the requested voice session."""


class VoiceSessionLifecycleConflict(Exception):
    """A terminal observation conflicts with canonical session authority."""


@dataclass(frozen=True, slots=True)
class VoiceSessionCompletionResult:
    """Stable canonical session and completion fact identities."""

    voice_session_id: UUID
    event_id: UUID
    changed: bool


async def record_voice_session_ended(
    *,
    organization_id: UUID,
    voice_session_id: UUID,
    runtime_mode: VoiceRuntimeMode,
    ended_at: datetime,
    ended_reason: str,
    status: VoiceSessionStatus,
    duration_ms: int | None = None,
    metrics: dict | None = None,
) -> VoiceSessionCompletionResult:
    """Commit terminal session truth and its durable reconciliation fact."""
    if status is VoiceSessionStatus.ACTIVE:
        raise VoiceSessionLifecycleConflict("A completion status must be terminal.")
    if duration_ms is not None and duration_ms < 0:
        raise VoiceSessionLifecycleConflict(
            "Voice session duration cannot be negative."
        )
    if not ended_reason.strip() or len(ended_reason) > 64:
        raise VoiceSessionLifecycleConflict(
            "Voice session ended_reason must contain 1 to 64 characters."
        )

    changed = False
    async with start_transaction() as session:
        voice_session = await session.scalar(
            select(VoiceSessionModel)
            .where(
                VoiceSessionModel.id == voice_session_id,
                VoiceSessionModel.organization_id == organization_id,
                VoiceSessionModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if voice_session is None:
            raise VoiceSessionAuthorityMissing
        if voice_session.runtime_mode != runtime_mode:
            raise VoiceSessionLifecycleConflict(
                "Voice session runtime mode conflicts with canonical authority."
            )
        if voice_session.status == VoiceSessionStatus.ACTIVE:
            if ended_at < voice_session.started_at:
                raise VoiceSessionLifecycleConflict(
                    "Voice session cannot end before it starts."
                )
            voice_session.status = status
            voice_session.ended_at = ended_at
            voice_session.ended_reason = ended_reason
            voice_session.duration_ms = (
                duration_ms
                if duration_ms is not None
                else max(
                    int((ended_at - voice_session.started_at).total_seconds() * 1000), 0
                )
            )
            voice_session.metrics = metrics
            changed = True
        elif voice_session.status != status or voice_session.ended_reason != ended_reason:
            logger.error(
                "Ignored conflicting voice session completion session=%s "
                "stored_status=%s observed_status=%s stored_reason=%s observed_reason=%s",
                voice_session.id,
                voice_session.status,
                status,
                voice_session.ended_reason,
                ended_reason,
            )
        if voice_session.ended_at is None:
            raise VoiceSessionLifecycleConflict(
                "Terminal voice session is missing ended_at."
            )

        event_id = uuid5(
            NAMESPACE_URL,
            f"eylo:{VOICE_SESSION_ENDED_EVENT_TYPE}:v1:"
            f"{organization_id}:{voice_session.id}",
        )
        await DurableEventService(session).file(
            envelope=DurableEventEnvelope(
                event_id=event_id,
                organization_id=organization_id,
                subject_type=VOICE_SESSION_SUBJECT_TYPE,
                subject_id=voice_session.id,
                event_type=VOICE_SESSION_ENDED_EVENT_TYPE,
                event_version=VOICE_SESSION_ENDED_EVENT_VERSION,
                occurred_at=voice_session.ended_at,
                recorded_at=voice_session.ended_at,
                correlation_id=voice_session.user_session_id,
                payload={
                    "conversation_id": str(voice_session.conversation_id),
                    "status": VoiceSessionStatus(voice_session.status).value,
                    "reason": voice_session.ended_reason,
                    "duration_ms": voice_session.duration_ms,
                },
            ),
            consumer_names=(VOICE_SESSION_COMPLETION_CONSUMER,),
        )

    try:
        spawned = await spawn_event_deliveries(
            organization_id=organization_id,
            event_id=event_id,
        )
    except Exception as error:  # noqa: BLE001 - PostgreSQL recovery owns binding
        logger.error(
            "Could not nudge voice session fact event=%s error_type=%s",
            event_id,
            type(error).__name__,
        )
    else:
        for delivery_id, _summary in spawned.failures:
            logger.error(
                "Could not nudge voice session delivery id=%s",
                delivery_id,
            )
    return VoiceSessionCompletionResult(
        voice_session_id=voice_session_id,
        event_id=event_id,
        changed=changed,
    )
