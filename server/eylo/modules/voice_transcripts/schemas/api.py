"""API schemas for voice transcript list and detail routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.voice_transcripts.constants import (
    VoiceAudioTrackKind,
    VoiceCanonicalState,
    VoiceRuntimeMode,
    VoiceSegmentRole,
    VoiceSegmentSource,
    VoiceSegmentType,
    VoiceSessionStatus,
    VoiceSpeechOutcome,
)


class VoiceTranscriptAudioUrls(EyloBaseApiSchema):
    user: str | None = None
    assistant: str | None = None
    combined: str | None = None


class VoiceSegmentResponse(EyloBaseApiSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    voice_session_id: UUID
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    sequence: int
    role: VoiceSegmentRole
    segment_type: VoiceSegmentType
    source: VoiceSegmentSource
    speech_outcome: VoiceSpeechOutcome | None = None
    text: str | None = None
    is_partial: bool = False
    language: str | None = None
    confidence: float | None = None
    words: list[dict[str, Any]] | None = None
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    duration_ms: int | None = None
    audio_track: VoiceAudioTrackKind | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: dict[str, Any] | None = None
    dtmf_digits: str | None = None
    redaction_state: str
    source_created_at: datetime | None = None
    created_at: datetime


class VoiceSessionSummary(EyloBaseApiSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    conversation_id: UUID
    agent_id: UUID | None = None
    agent_revision: int | None = None
    session_id: str
    runtime_mode: VoiceRuntimeMode
    transport: str
    status: VoiceSessionStatus
    canonical_state: VoiceCanonicalState
    canonical_redaction_version: int | None = None
    canonical_failure_code: str | None = None
    canonical_source_complete: bool | None = None
    canonical_projected_at: datetime | None = None
    canonical_message_count: int = 0
    started_at: datetime
    ended_at: datetime | None = None
    ended_reason: str | None = None
    duration_ms: int | None = None
    segment_count: int = 0
    user_talk_time_ms: int | None = None
    assistant_talk_time_ms: int | None = None
    stt_vendor: str | None = None
    stt_model: str | None = None
    tts_vendor: str | None = None
    tts_model: str | None = None
    tts_voice: str | None = None
    realtime_vendor: str | None = None
    realtime_model: str | None = None
    telephony_provider: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    created_at: datetime


class VoiceSessionListResponse(EyloBaseApiSchema):
    data: list[VoiceSessionSummary]
    total: int
    page: int
    limit: int
    has_more: bool = False


class VoiceSessionDetail(VoiceSessionSummary):
    user_audio_url: str | None = None
    assistant_audio_url: str | None = None
    combined_audio_url: str | None = None
    audio_urls: VoiceTranscriptAudioUrls = Field(
        default_factory=VoiceTranscriptAudioUrls
    )
    segments: list[VoiceSegmentResponse] = Field(default_factory=list)
    segment_total: int = 0
    segment_page: int = 1
    segment_limit: int = 100
    segments_has_more: bool = False
    metrics: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class VoiceSessionFilter(EyloBaseApiSchema):
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    status: VoiceSessionStatus | None = None
    runtime_mode: VoiceRuntimeMode | None = None
