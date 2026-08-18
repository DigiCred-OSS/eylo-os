"""Conversation-to-session TTS routing.

WebSocket managers own connection/session transport mechanics. This module owns
the voice-pipeline step that turns conversation-level TTS payloads into per
session TTS manager queue items and request-state updates.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceDraft,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.request_state import (
    VoiceRequestSource,
    VoiceRequestStatus,
)

logger = logging.getLogger(__name__)

_PAYLOAD_TYPE_FIELD = "type"
_PAYLOAD_TEXT_FIELD = "text"
_PAYLOAD_TURN_ID_FIELD = "turn_id"
_PAYLOAD_REQUEST_ID_FIELD = "request_id"
_PAYLOAD_POLICY_SOURCE_FIELD = "policy_source"
_PAYLOAD_TYPE_TEXT = "text"
_PAYLOAD_TYPE_FINALIZE = "finalize"


class TTSQueue(Protocol):
    async def add_to_request_queue(self, item: str | dict[str, Any]) -> None: ...


class VoiceSessionState(Protocol):
    tts_socket: TTSQueue | None
    live_voice_buffer: LiveVoiceBuffer | None

    def start_voice_request(
        self,
        *,
        request_id: UUID,
        conversation_id: UUID,
        source: VoiceRequestSource,
        status: VoiceRequestStatus,
    ) -> Any: ...

    def mark_voice_request(
        self,
        request_id: UUID | str | None,
        status: VoiceRequestStatus,
        *,
        conversation_id: UUID | None = None,
        turn_id: str | None = None,
    ) -> Any | None: ...


class ConversationSessionRouter(Protocol):
    async def get_sessions_for_conversation(
        self,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> list[str]: ...

    def get_session_state(
        self,
        organization_id: UUID,
        session_id: str,
    ) -> VoiceSessionState | None: ...


def build_tts_queue_item(payload: str | dict[str, Any]) -> str | dict[str, Any] | None:
    """Normalize conversation-level TTS payloads for TTS manager queues."""
    if isinstance(payload, str):
        return payload

    payload_type = payload.get(_PAYLOAD_TYPE_FIELD)
    if payload_type == _PAYLOAD_TYPE_TEXT:
        return {
            _PAYLOAD_TYPE_FIELD: _PAYLOAD_TYPE_TEXT,
            _PAYLOAD_TEXT_FIELD: payload.get(_PAYLOAD_TEXT_FIELD),
            _PAYLOAD_TURN_ID_FIELD: payload.get(_PAYLOAD_TURN_ID_FIELD),
            _PAYLOAD_REQUEST_ID_FIELD: payload.get(_PAYLOAD_REQUEST_ID_FIELD),
            _PAYLOAD_POLICY_SOURCE_FIELD: payload.get(_PAYLOAD_POLICY_SOURCE_FIELD),
        }
    if payload_type == _PAYLOAD_TYPE_FINALIZE:
        return {
            _PAYLOAD_TYPE_FIELD: _PAYLOAD_TYPE_FINALIZE,
            _PAYLOAD_TURN_ID_FIELD: payload.get(_PAYLOAD_TURN_ID_FIELD),
            _PAYLOAD_REQUEST_ID_FIELD: payload.get(_PAYLOAD_REQUEST_ID_FIELD),
            _PAYLOAD_POLICY_SOURCE_FIELD: payload.get(_PAYLOAD_POLICY_SOURCE_FIELD),
        }

    return None


async def enqueue_conversation_tts_payload(
    *,
    router: ConversationSessionRouter,
    conversation_id: UUID | str,
    organization_id: UUID | str,
    payload: str | dict[str, Any],
) -> None:
    """Enqueue a conversation-level TTS payload into all active voice sessions."""
    normalized_conversation_id = UUID(str(conversation_id))
    normalized_organization_id = UUID(str(organization_id))
    session_ids = await router.get_sessions_for_conversation(
        normalized_organization_id,
        normalized_conversation_id,
    )

    if not session_ids:
        logger.debug("[TTS_PIPELINE] No session_ids for conversation, skipping TTS")
        return

    tts_item = build_tts_queue_item(payload)
    if tts_item is None:
        logger.warning("[TTS_PIPELINE] tts_item is None, cannot enqueue")
        return

    for session_id in session_ids:
        session_state = router.get_session_state(
            normalized_organization_id,
            str(session_id),
        )
        if not session_state:
            continue

        tts_socket = session_state.tts_socket
        if tts_socket is None:
            logger.debug(
                "[TTS_PIPELINE] session %s: tts_socket is None, skipping",
                session_id,
            )
            continue

        if isinstance(tts_item, dict):
            await _capture_policy_speech(
                session_state=session_state,
                conversation_id=normalized_conversation_id,
                item=tts_item,
            )
            request_id = tts_item.get(_PAYLOAD_REQUEST_ID_FIELD)
            session_state.mark_voice_request(
                request_id,
                VoiceRequestStatus.TTS_QUEUED,
                conversation_id=normalized_conversation_id,
                turn_id=tts_item.get(_PAYLOAD_TURN_ID_FIELD),
            )

        logger.debug(
            "[TTS_PIPELINE] Enqueuing to TTS request_queue: type=%s",
            tts_item.get(_PAYLOAD_TYPE_FIELD) if isinstance(tts_item, dict) else "str",
        )
        await tts_socket.add_to_request_queue(tts_item)


async def _capture_policy_speech(
    *,
    session_state: VoiceSessionState,
    conversation_id: UUID,
    item: dict[str, Any],
) -> None:
    if item.get(_PAYLOAD_TYPE_FIELD) != _PAYLOAD_TYPE_TEXT:
        return
    policy_source = item.get(_PAYLOAD_POLICY_SOURCE_FIELD)
    request_id = item.get(_PAYLOAD_REQUEST_ID_FIELD)
    text = item.get(_PAYLOAD_TEXT_FIELD)
    if policy_source is None:
        return
    try:
        source = VoiceRequestSource(str(policy_source))
        normalized_request_id = UUID(str(request_id))
    except (TypeError, ValueError):
        logger.error("Policy TTS payload has invalid request authority.")
        return
    if not isinstance(text, str) or not text or session_state.live_voice_buffer is None:
        logger.error("Policy TTS payload cannot be captured in live voice state.")
        return

    session_state.start_voice_request(
        request_id=normalized_request_id,
        conversation_id=conversation_id,
        source=source,
        status=VoiceRequestStatus.TTS_QUEUED,
    )
    await session_state.live_voice_buffer.append_turn(
        [
            LiveVoiceDraft(
                kind=LiveVoiceItemKind.SYSTEM_SPEECH,
                payload=text,
                request_id=normalized_request_id,
                policy_source=source,
            )
        ]
    )
