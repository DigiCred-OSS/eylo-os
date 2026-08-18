"""File canonical voice-message facts inside the message transaction."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.messages import MessageKind, RequestStatus
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_SESSION_ROW_ID,
    VOICE_MESSAGE_META_SPEECH_OUTCOME,
)
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventService
from eylo.events.durable.voice_contracts import (
    VOICE_MESSAGE_EVENT_TYPE,
    VOICE_MESSAGE_EVENT_VERSION,
    VOICE_MESSAGE_SEGMENT_CONSUMER,
    VOICE_MESSAGE_SUBJECT_TYPE,
)
from eylo.modules.conversations.models.conversations import ConversationsModel

_ASSISTANT_TERMINAL_STATUSES = frozenset(
    {
        RequestStatus.COMPLETED.value,
        RequestStatus.FAILED.value,
        RequestStatus.INTERRUPTED.value,
        RequestStatus.SKIPPED.value,
    }
)


async def file_voice_message_fact(
    *,
    session: AsyncSession,
    message,
) -> UUID | None:
    """File one stable fact when a canonical message is a final V1 voice class."""
    if not _is_final_voice_timeline_message(message):
        return None
    organization_id = await session.scalar(
        select(ConversationsModel.organization_id).where(
            ConversationsModel.id == message.conversation_id,
            ConversationsModel.deleted.is_(False),
        )
    )
    if organization_id is None:
        raise ValueError("Canonical voice message conversation is unavailable.")

    occurred_at = _require_datetime(message.created_at)
    recorded_at = _recorded_at(message, occurred_at)
    event_id = uuid5(
        NAMESPACE_URL,
        f"eylo:{VOICE_MESSAGE_EVENT_TYPE}:v1:{organization_id}:{message.id}",
    )
    await DurableEventService(session).file(
        envelope=DurableEventEnvelope(
            event_id=event_id,
            organization_id=organization_id,
            subject_type=VOICE_MESSAGE_SUBJECT_TYPE,
            subject_id=message.id,
            event_type=VOICE_MESSAGE_EVENT_TYPE,
            event_version=VOICE_MESSAGE_EVENT_VERSION,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            payload={},
        ),
        consumer_names=(VOICE_MESSAGE_SEGMENT_CONSUMER,),
    )
    return event_id


def _is_final_voice_timeline_message(message) -> bool:
    meta = _meta(message)
    if not meta.get(VOICE_MESSAGE_META_SESSION_ROW_ID):
        return False
    kind = _enum_value(message.kind)
    if kind in {MessageKind.USER.value, MessageKind.TOOL_USE.value}:
        return True
    if kind != MessageKind.ASSISTANT.value:
        return False
    if meta.get(VOICE_MESSAGE_META_SPEECH_OUTCOME) is not None:
        return True
    status = _enum_value(message.request_status)
    return status in _ASSISTANT_TERMINAL_STATUSES


def _meta(message) -> dict:
    raw = message.meta
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return raw.model_dump(exclude_none=True)
    return {}


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _require_datetime(value) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("Canonical voice message is missing created_at.")
    return value


def _recorded_at(message, occurred_at: datetime) -> datetime:
    meta = _meta(message)
    kind = _enum_value(message.kind)
    if (
        kind == MessageKind.ASSISTANT.value
        and meta.get(VOICE_MESSAGE_META_SPEECH_OUTCOME) is None
    ):
        updated_at = getattr(message, "updated_at", None)
        if isinstance(updated_at, datetime):
            return max(updated_at, occurred_at)
    return occurred_at
