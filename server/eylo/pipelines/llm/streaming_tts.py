"""Ordered LLM-to-voice runtime routing.

The conversation runner awaits this module directly because speech chunks and
their terminal marker must preserve model order. Lossy lifecycle events remain
presentation-only and never drive TTS, filler, or voice request state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from eylo.modules.conversations.schemas.conversations import ConversationInDb
from eylo.modules.conversations.schemas.messages import MessageInDb, MessageKind
from eylo.modules.conversations.services.messages import MessageService
from eylo.pipelines.voice.filler import FillerPhraseManager
from eylo.pipelines.voice.interaction_state import VoiceInteractionState
from eylo.pipelines.voice.request_state import VoiceRequestStatus
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceTextSegment:
    """One ordered LLM-to-TTS delivery unit for an active voice turn."""

    organization_id: UUID
    conversation_id: UUID
    text: str
    is_complete: bool
    turn_id: str | None = None
    request_id: str | None = None


async def push_voice_message_to_tts(
    message: MessageInDb,
    conversation: ConversationInDb,
) -> None:
    """Push non-streamed assistant messages into TTS for active voice sessions."""
    if message.kind != MessageKind.ASSISTANT:
        return

    logger.debug("Broadcasting created message to TTS")
    message_text = MessageService.get_message_content(message.content)

    await S_ws_manager.conversation_tts_to_session(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        payload={"type": "text", "text": message_text},
    )


async def prepare_voice_sessions_for_inference(
    *,
    conversation_id: UUID,
    organization_id: UUID,
    request_id: UUID | str | None,
) -> None:
    """Schedule filler and mark active voice sessions as thinking."""
    try:
        await FillerPhraseManager.schedule_filler(conversation_id, organization_id)
        await set_thinking_state(conversation_id, organization_id, True)
        await mark_voice_request_state(
            conversation_id=conversation_id,
            organization_id=organization_id,
            request_id=request_id,
            status=VoiceRequestStatus.LLM_STARTED,
        )
    except Exception:
        logger.warning("Could not prepare active voice sessions for inference")


async def complete_voice_sessions_for_response(
    *,
    conversation_id: UUID,
    organization_id: UUID,
    request_id: UUID | str | None,
) -> None:
    """Cancel filler and mark active voice sessions as no longer thinking."""
    try:
        FillerPhraseManager.cancel_filler(conversation_id)
        await set_thinking_state(conversation_id, organization_id, False)
        await mark_voice_request_state(
            conversation_id=conversation_id,
            organization_id=organization_id,
            request_id=request_id,
            status=VoiceRequestStatus.LLM_COMPLETED,
        )
        await finish_idle_voice_activity(conversation_id, organization_id)
    except Exception:
        logger.warning("Could not complete active voice session inference state")


async def deliver_voice_text_segment(segment: VoiceTextSegment) -> None:
    """Deliver one segment directly so event scheduling cannot reorder speech."""
    FillerPhraseManager.cancel_filler(segment.conversation_id)

    try:
        await set_thinking_state(
            segment.conversation_id,
            segment.organization_id,
            False,
        )
        await mark_voice_request_state(
            conversation_id=segment.conversation_id,
            organization_id=segment.organization_id,
            request_id=segment.request_id,
            status=VoiceRequestStatus.LLM_STREAMING,
            turn_id=segment.turn_id,
        )
    except Exception:
        logger.warning("Could not clear thinking state")

    if segment.text and segment.text.strip():
        logger.debug(
            "[TTS_PIPELINE] Token -> pubsub chars=%d (turn_id=%s)",
            len(segment.text),
            segment.turn_id,
        )
        await S_ws_manager.conversation_tts_to_session(
            conversation_id=segment.conversation_id,
            organization_id=segment.organization_id,
            payload={
                "type": "text",
                "text": segment.text,
                "turn_id": segment.turn_id,
                "request_id": segment.request_id,
            },
        )

    if segment.is_complete:
        logger.info(
            "[TTS_PIPELINE] LLM complete -> finalize (turn_id=%s)",
            segment.turn_id,
        )
        await S_ws_manager.conversation_tts_to_session(
            conversation_id=segment.conversation_id,
            organization_id=segment.organization_id,
            payload={
                "type": "finalize",
                "turn_id": segment.turn_id,
                "request_id": segment.request_id,
            },
        )


async def set_thinking_state(
    conversation_id,
    organization_id,
    thinking: bool,
) -> None:
    """Set ``is_agent_thinking`` on every voice session for a conversation."""
    session_ids = await S_ws_manager.get_sessions_for_conversation(
        organization_id,
        conversation_id,
    )
    for session_id in session_ids:
        session_state = S_ws_manager.get_session_state(organization_id, str(session_id))
        if session_state and not session_state.voice_termination_reason:
            session_state.is_agent_thinking = thinking
            if thinking:
                session_state.voice_activity_gate.mark_agent_activity_started()
                if session_state.voice_interaction_callback:
                    session_state.voice_interaction_callback(
                        VoiceInteractionState.PROCESSING
                    )


async def finish_idle_voice_activity(
    conversation_id,
    organization_id,
) -> None:
    """Mark voice sessions as awaiting the user when no TTS turn is active."""
    session_ids = await S_ws_manager.get_sessions_for_conversation(
        organization_id,
        conversation_id,
    )
    for session_id in session_ids:
        session_state = S_ws_manager.get_session_state(organization_id, str(session_id))
        if not session_state:
            continue
        tts = session_state.tts_manager or session_state.tts_socket
        if (
            not bool(tts and tts.is_playback_active())
            and not session_state.transport_playback_gate.is_active
        ):
            already_awaiting_user = session_state.voice_activity_gate.is_awaiting_user
            session_state.voice_activity_gate.mark_agent_activity_finished()
            if (
                not already_awaiting_user
                and session_state.voice_interaction_callback
            ):
                session_state.voice_interaction_callback(
                    VoiceInteractionState.LISTENING
                )


async def mark_voice_request_state(
    *,
    conversation_id,
    organization_id,
    request_id,
    status: VoiceRequestStatus,
    turn_id: str | None = None,
) -> None:
    if request_id is None:
        return

    session_ids = await S_ws_manager.get_sessions_for_conversation(
        organization_id,
        conversation_id,
    )
    for session_id in session_ids:
        session_state = S_ws_manager.get_session_state(organization_id, str(session_id))
        if session_state:
            session_state.mark_voice_request(
                request_id,
                status,
                conversation_id=conversation_id,
                turn_id=turn_id,
            )
