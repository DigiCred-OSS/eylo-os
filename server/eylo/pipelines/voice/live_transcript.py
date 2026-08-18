"""Conversation-scoped, ephemeral presentation of live voice transcripts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from eylo.common.contracts.message_content import (
    AssistantMessageContent,
    TextContent,
    UserMessageContent,
)
from eylo.common.contracts.messages import MessageContentKind, MessageKind, MessageMeta
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_RUNTIME_MODE,
    VOICE_MESSAGE_META_SESSION_ID,
    VOICE_MESSAGE_META_SESSION_ROW_ID,
    VOICE_MESSAGE_META_SOURCE_SEQUENCE,
)
from eylo.common.contracts.websocket import WsEventAction
from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBufferIdentity,
    LiveVoiceItem,
    LiveVoiceItemKind,
)

logger = logging.getLogger(__name__)

_BROWSER_MODES = {
    VoiceRuntimeMode.BROWSER_DECOMPOSED,
    VoiceRuntimeMode.BROWSER_REALTIME,
}
_DELIVERY_TIMEOUT_SECONDS = 1.0
_DELIVERY_TASKS: set[asyncio.Task[None]] = set()


class LiveMessageTranscript(EyloBaseApiSchema):
    """Message-shaped raw UI delta that is never a durable conversation fact."""

    id: UUID
    conversation_id: UUID
    sender_participant_id: UUID
    kind: MessageKind
    content_kind: MessageContentKind = MessageContentKind.TEXT
    content: UserMessageContent | AssistantMessageContent
    meta: MessageMeta
    external_id: str
    request_id: UUID | None = None
    created_at: datetime


def schedule_live_message_transcripts(
    identity: LiveVoiceBufferIdentity,
    items: tuple[LiveVoiceItem, ...],
) -> None:
    """Schedule best-effort UI deltas without delaying the voice loop."""
    if (
        identity.runtime_mode not in _BROWSER_MODES
        or identity.voice_session_id is None
        or identity.contact_id is None
    ):
        return

    for item in items:
        payload = _message_payload(identity, item)
        if payload is None:
            continue
        task = asyncio.create_task(
            _deliver_live_message_transcript(
                contact_id=identity.contact_id,
                organization_id=identity.organization_id,
                conversation_id=identity.conversation_id,
                sequence=item.sequence,
                payload=payload,
            ),
            name=f"live-message-transcript-{item.sequence}",
        )
        _DELIVERY_TASKS.add(task)
        task.add_done_callback(_DELIVERY_TASKS.discard)


async def _deliver_live_message_transcript(
    *,
    contact_id: UUID,
    organization_id: UUID,
    conversation_id: UUID,
    sequence: int,
    payload: LiveMessageTranscript,
) -> None:
    # Local import prevents websocket schema initialization from cycling back
    # through the realtime voice manager during application startup.
    from eylo.pipelines.websocket.singleton import S_ws_manager

    try:
        async with asyncio.timeout(_DELIVERY_TIMEOUT_SECONDS):
            await S_ws_manager.reply_to_conversation_contact(
                contact_id=contact_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                kind=WsEventAction.MESSAGE_TRANSCRIPT,
                payload=payload.model_dump(by_alias=True),
            )
    except Exception as error:  # noqa: BLE001 - presentation cannot stop voice
        logger.error(
            "Live voice transcript delivery failed organization_id=%s "
            "conversation_id=%s sequence=%s error_type=%s",
            organization_id,
            conversation_id,
            sequence,
            type(error).__name__,
        )


def _message_payload(
    identity: LiveVoiceBufferIdentity,
    item: LiveVoiceItem,
) -> LiveMessageTranscript | None:
    if not isinstance(item.payload, str):
        return None
    if item.kind is LiveVoiceItemKind.USER_TRANSCRIPT:
        participant_id = identity.contact_participant_id
        kind = MessageKind.USER
        content = UserMessageContent(content=[TextContent(text=item.payload)])
    elif item.kind is LiveVoiceItemKind.ASSISTANT_TRANSCRIPT:
        participant_id = identity.agent_participant_id
        kind = MessageKind.ASSISTANT
        content = AssistantMessageContent(content=[TextContent(text=item.payload)])
    else:
        return None
    if participant_id is None or item.participant_id not in {None, participant_id}:
        return None

    external_id = f"voice:{identity.voice_session_id}:{item.sequence}"
    transient_id = uuid5(
        NAMESPACE_URL,
        f"eylo:live-transcript:{identity.organization_id}:{external_id}",
    )
    meta: dict[str, Any] = {
        "transient": True,
        VOICE_MESSAGE_META_SESSION_ID: identity.session_id,
        VOICE_MESSAGE_META_SESSION_ROW_ID: str(identity.voice_session_id),
        VOICE_MESSAGE_META_RUNTIME_MODE: identity.runtime_mode.value,
        VOICE_MESSAGE_META_SOURCE_SEQUENCE: item.sequence,
    }
    return LiveMessageTranscript(
        id=transient_id,
        conversation_id=identity.conversation_id,
        sender_participant_id=participant_id,
        kind=kind,
        content=content,
        meta=MessageMeta.model_validate(meta),
        external_id=external_id,
        request_id=item.request_id,
        created_at=item.occurred_at,
    )


__all__ = ["LiveMessageTranscript", "schedule_live_message_transcripts"]
