"""Derive voice-request lifecycle from message and playback state."""

from enum import StrEnum
from uuid import UUID

import arrow
from pydantic import BaseModel, Field


class VoiceRequestSource(StrEnum):
    USER = "user"
    FILLER = "filler"
    GREETING = "greeting"
    CONSENT = "consent"
    SILENCE = "silence"
    END_CALL = "end_call"
    MAX_DURATION = "max_duration"


class VoiceRequestStatus(StrEnum):
    STT_DETECTED = "stt_detected"
    USER_TRANSCRIBING = "user_transcribing"
    LIVE_INPUT_BUFFERED = "live_input_buffered"
    LLM_STARTED = "llm_started"
    LLM_STREAMING = "llm_streaming"
    LLM_COMPLETED = "llm_completed"
    TTS_QUEUED = "tts_queued"
    TTS_PLAYING = "tts_playing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class VoiceRequestState(BaseModel):
    request_id: UUID
    conversation_id: UUID
    source: VoiceRequestSource = VoiceRequestSource.USER
    status: VoiceRequestStatus = VoiceRequestStatus.STT_DETECTED
    user_message_id: UUID | None = None
    assistant_message_id: UUID | None = None
    turn_id: str | None = None
    started_at: float = Field(default_factory=lambda: arrow.utcnow().timestamp())
    updated_at: float = Field(default_factory=lambda: arrow.utcnow().timestamp())

    def mark(
        self,
        status: VoiceRequestStatus,
        *,
        user_message_id: UUID | None = None,
        assistant_message_id: UUID | None = None,
        turn_id: str | None = None,
    ) -> None:
        self.status = status
        if user_message_id is not None:
            self.user_message_id = user_message_id
        if assistant_message_id is not None:
            self.assistant_message_id = assistant_message_id
        if turn_id is not None:
            self.turn_id = turn_id
        self.updated_at = arrow.utcnow().timestamp()


_TERMINAL_STATUSES = {
    VoiceRequestStatus.COMPLETED,
    VoiceRequestStatus.INTERRUPTED,
    VoiceRequestStatus.FAILED,
}

_STATUS_ORDER = {
    VoiceRequestStatus.STT_DETECTED: 10,
    VoiceRequestStatus.USER_TRANSCRIBING: 20,
    VoiceRequestStatus.LIVE_INPUT_BUFFERED: 30,
    VoiceRequestStatus.LLM_STARTED: 40,
    VoiceRequestStatus.LLM_STREAMING: 50,
    VoiceRequestStatus.LLM_COMPLETED: 60,
    VoiceRequestStatus.TTS_QUEUED: 70,
    VoiceRequestStatus.TTS_PLAYING: 80,
    VoiceRequestStatus.COMPLETED: 90,
    VoiceRequestStatus.INTERRUPTED: 90,
    VoiceRequestStatus.FAILED: 90,
}


def resolve_voice_request_status(
    current: VoiceRequestStatus,
    incoming: VoiceRequestStatus,
) -> VoiceRequestStatus:
    if incoming in _TERMINAL_STATUSES:
        return incoming
    if current in _TERMINAL_STATUSES:
        return current
    if _STATUS_ORDER[incoming] < _STATUS_ORDER[current]:
        return current
    return incoming
