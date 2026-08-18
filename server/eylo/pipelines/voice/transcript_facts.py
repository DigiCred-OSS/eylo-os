"""Durable consumers for canonical voice session and timeline facts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import DurableState
from eylo.common.contracts.messages import MessageInDb
from eylo.common.contracts.voice import VOICE_MESSAGE_META_SESSION_ROW_ID
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.registry import (
    EventConsumerRegistry,
    PermanentEventConsumerError,
)
from eylo.events.durable.voice_contracts import (
    VOICE_MESSAGE_EVENT_TYPE,
    VOICE_MESSAGE_EVENT_VERSION,
    VOICE_MESSAGE_SEGMENT_CONSUMER,
    VOICE_MESSAGE_SUBJECT_TYPE,
    VOICE_RECORDING_ATTACHMENT_CONSUMER,
    VOICE_RECORDING_AVAILABLE_EVENT_TYPE,
    VOICE_RECORDING_AVAILABLE_EVENT_VERSION,
    VOICE_RECORDING_SUBJECT_TYPE,
    VOICE_SESSION_COMPLETION_CONSUMER,
    VOICE_SESSION_ENDED_EVENT_TYPE,
    VOICE_SESSION_ENDED_EVENT_VERSION,
    VOICE_SESSION_SUBJECT_TYPE,
)
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.voice.recording.model import VoiceRecordingModel
from eylo.modules.voice_transcripts.constants import VoiceSessionStatus
from eylo.modules.voice_transcripts.models import VoiceSessionModel
from eylo.modules.voice_transcripts.schemas.indb import VoiceSessionInDb
from eylo.modules.voice_transcripts.services.indb import VoiceTranscriptService


def register_voice_transcript_consumers(registry: EventConsumerRegistry) -> None:
    """Register exact V1 message, session, and recording consumers."""
    registry.register(
        consumer_name=VOICE_MESSAGE_SEGMENT_CONSUMER,
        event_type=VOICE_MESSAGE_EVENT_TYPE,
        event_version=VOICE_MESSAGE_EVENT_VERSION,
        handler=consume_voice_message_segment,
    )
    registry.register(
        consumer_name=VOICE_SESSION_COMPLETION_CONSUMER,
        event_type=VOICE_SESSION_ENDED_EVENT_TYPE,
        event_version=VOICE_SESSION_ENDED_EVENT_VERSION,
        handler=consume_voice_session_completion,
    )
    registry.register(
        consumer_name=VOICE_RECORDING_ATTACHMENT_CONSUMER,
        event_type=VOICE_RECORDING_AVAILABLE_EVENT_TYPE,
        event_version=VOICE_RECORDING_AVAILABLE_EVENT_VERSION,
        handler=consume_voice_recording_attachment,
    )


async def consume_voice_message_segment(
    session: AsyncSession,
    envelope: DurableEventEnvelope,
) -> None:
    """Reload canonical message/session state and project one V1 segment."""
    if envelope.subject_type != VOICE_MESSAGE_SUBJECT_TYPE:
        raise PermanentEventConsumerError(
            "Durable voice message fact has an unsupported subject type."
        )
    row = (
        await session.execute(
            select(MessagesModel, ConversationsModel)
            .join(
                ConversationsModel,
                ConversationsModel.id == MessagesModel.conversation_id,
            )
            .where(
                MessagesModel.id == envelope.subject_id,
                MessagesModel.deleted.is_(False),
                ConversationsModel.organization_id == envelope.organization_id,
                ConversationsModel.deleted.is_(False),
            )
        )
    ).one_or_none()
    if row is None:
        raise PermanentEventConsumerError(
            "Canonical voice message authority is unavailable."
        )
    message_row, conversation = row
    meta = message_row.meta or {}
    try:
        voice_session_id = UUID(str(meta[VOICE_MESSAGE_META_SESSION_ROW_ID]))
    except (KeyError, TypeError, ValueError) as error:
        raise PermanentEventConsumerError(
            "Canonical voice message has no exact session authority."
        ) from error

    voice_session = await session.scalar(
        select(VoiceSessionModel)
        .where(
            VoiceSessionModel.id == voice_session_id,
            VoiceSessionModel.organization_id == envelope.organization_id,
            VoiceSessionModel.conversation_id == conversation.id,
            VoiceSessionModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if voice_session is None:
        raise PermanentEventConsumerError(
            "Canonical voice session authority is unavailable."
        )
    try:
        segment = await VoiceTranscriptService(session).create_segment_from_canonical_message(
            voice_session=VoiceSessionInDb.model_validate(voice_session),
            message=MessageInDb.model_validate(message_row),
        )
    except ValueError as error:
        raise PermanentEventConsumerError(str(error)) from error
    if segment is None:
        raise PermanentEventConsumerError(
            "Canonical message is outside the V1 voice timeline classes."
        )


async def consume_voice_session_completion(
    session: AsyncSession,
    envelope: DurableEventEnvelope,
) -> None:
    """Recompute terminal rollups without relying on fact arrival order."""
    if envelope.subject_type != VOICE_SESSION_SUBJECT_TYPE:
        raise PermanentEventConsumerError(
            "Durable voice session fact has an unsupported subject type."
        )
    voice_session = await session.scalar(
        select(VoiceSessionModel)
        .where(
            VoiceSessionModel.id == envelope.subject_id,
            VoiceSessionModel.organization_id == envelope.organization_id,
            VoiceSessionModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if (
        voice_session is None
        or voice_session.status == VoiceSessionStatus.ACTIVE
        or voice_session.ended_at is None
    ):
        raise PermanentEventConsumerError(
            "Canonical terminal voice session authority is unavailable."
        )
    completed = await VoiceTranscriptService(session).reconcile_completed_session(
        organization_id=envelope.organization_id,
        voice_session_id=envelope.subject_id,
    )
    if completed is None:
        raise PermanentEventConsumerError(
            "Canonical voice session rollup could not be reconciled."
        )


async def consume_voice_recording_attachment(
    session: AsyncSession,
    envelope: DurableEventEnvelope,
) -> None:
    """Attach canonical recording refs without trusting event payload data."""
    if envelope.subject_type != VOICE_RECORDING_SUBJECT_TYPE:
        raise PermanentEventConsumerError(
            "Durable voice recording fact has an unsupported subject type."
        )
    recording = await session.scalar(
        select(VoiceRecordingModel).where(
            VoiceRecordingModel.id == envelope.subject_id,
            VoiceRecordingModel.organization_id == envelope.organization_id,
            VoiceRecordingModel.state == DurableState.SUCCEEDED,
            VoiceRecordingModel.deleted.is_(False),
        )
    )
    if recording is None:
        raise PermanentEventConsumerError(
            "Canonical voice recording authority is unavailable."
        )
    voice_session = await session.scalar(
        select(VoiceSessionModel)
        .where(
            VoiceSessionModel.id == recording.voice_session_id,
            VoiceSessionModel.organization_id == envelope.organization_id,
            VoiceSessionModel.conversation_id == recording.conversation_id,
            VoiceSessionModel.session_id == recording.session_id,
            (
                VoiceSessionModel.user_session_id == envelope.correlation_id
                if envelope.correlation_id is not None
                else VoiceSessionModel.user_session_id.is_(None)
            ),
            VoiceSessionModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if voice_session is None:
        raise PermanentEventConsumerError(
            "Canonical voice session authority is unavailable."
        )

    recording_id = UUID(str(recording.id))
    expected = {
        "user_audio_url": None,
        "assistant_audio_url": None,
        "user_audio_recording_id": (
            recording_id if recording.user_storage_key is not None else None
        ),
        "assistant_audio_recording_id": (
            recording_id if recording.agent_storage_key is not None else None
        ),
        "audio_format": "wav",
    }
    for field, value in expected.items():
        current = getattr(voice_session, field)
        if current is not None and current != value:
            raise PermanentEventConsumerError(
                "Canonical voice session has conflicting recording authority."
            )
        setattr(voice_session, field, value)
