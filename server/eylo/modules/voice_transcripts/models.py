"""SQLAlchemy models for voice transcript sessions and timeline segments."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eylo.common.models import EyloBaseModel, EyloOrganizationModel
from eylo.modules.voice_transcripts.constants import (
    VoiceAudioTrackKind,
    VoiceCanonicalState,
    VoiceRuntimeMode,
    VoiceSegmentRole,
    VoiceSegmentSource,
    VoiceSegmentType,
    VoiceSessionStatus,
)


class VoiceSessionModel(EyloOrganizationModel):
    """Durable metadata for one browser or telephony voice conversation."""

    __tablename__ = "voice_sessions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "organization_id",
            "session_id",
            "runtime_mode",
            name="uq_voice_sessions_org_session_mode",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            "session_id",
            name="uq_voice_sessions_recording_owner",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_voice_sessions_segment_owner",
        ),
        ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_voice_sessions_user_session_conversation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["telephony_call_id", "organization_id", "conversation_id"],
            [
                "telephony_calls.id",
                "telephony_calls.organization_id",
                "telephony_calls.conversation_id",
            ],
            name="fk_voice_sessions_call_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_voice_sessions_agent_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(agent_id IS NULL AND agent_revision IS NULL) OR "
            "(agent_id IS NOT NULL AND agent_revision > 0)",
            name="ck_voice_sessions_agent_ref",
        ),
        CheckConstraint(
            "canonical_state IN "
            "('not_run', 'clean', 'redacted', 'failed', 'no_storage')",
            name="ck_voice_sessions_canonical_state",
        ),
        CheckConstraint(
            "canonical_redaction_version IS NULL OR canonical_redaction_version > 0",
            name="ck_voice_sessions_canonical_redaction_version",
        ),
        CheckConstraint(
            "canonical_message_count >= 0",
            name="ck_voice_sessions_canonical_message_count",
        ),
        CheckConstraint(
            "ended_reason IS NULL OR length(btrim(ended_reason)) > 0",
            name="ck_voice_sessions_ended_reason",
        ),
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL "
            "AND ended_reason IS NULL AND duration_ms IS NULL) OR "
            "(status IN ('completed', 'failed') AND ended_at IS NOT NULL "
            "AND ended_reason IS NOT NULL AND duration_ms >= 0)",
            name="ck_voice_sessions_terminal_state",
        ),
        Index("ix_voice_sessions_org_started", "organization_id", "started_at"),
        Index(
            "ix_voice_sessions_org_conversation", "organization_id", "conversation_id"
        ),
        Index(
            "ix_voice_sessions_org_agent_started",
            "organization_id",
            "agent_id",
            "started_at",
        ),
        Index(
            "ix_voice_sessions_org_status_started",
            "organization_id",
            "status",
            "started_at",
        ),
        Index(
            "ix_voice_sessions_org_telephony_call",
            "organization_id",
            "telephony_call_id",
        ),
    )

    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_session_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    agent_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    agent_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    runtime_mode: Mapped[VoiceRuntimeMode] = mapped_column(String(64), nullable=False)
    transport: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VoiceSessionStatus] = mapped_column(
        String(32), nullable=False, default=VoiceSessionStatus.ACTIVE
    )
    canonical_state: Mapped[VoiceCanonicalState] = mapped_column(
        String(32), nullable=False, default=VoiceCanonicalState.NOT_RUN
    )
    canonical_redaction_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    canonical_failure_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    canonical_source_complete: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    canonical_projected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canonical_message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_audio_recording_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    assistant_audio_recording_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    combined_audio_recording_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    user_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    combined_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_format: Mapped[str | None] = mapped_column(String(64), nullable=True)

    stt_vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stt_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tts_vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tts_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tts_voice: Mapped[str | None] = mapped_column(String(128), nullable=True)
    realtime_vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    realtime_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    telephony_call_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    provider_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephony_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    from_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    recording_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    recording_consent: Mapped[str | None] = mapped_column(String(32), nullable=True)

    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_segment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    user_talk_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assistant_talk_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silence_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dtmf_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transfer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    segments: Mapped[list["VoiceSegmentModel"]] = relationship(
        back_populates="voice_session", cascade="all, delete-orphan"
    )


class VoiceSegmentModel(EyloBaseModel):
    """Ordered timeline entry for a voice transcript session."""

    __tablename__ = "voice_segments"

    __table_args__ = (
        ForeignKeyConstraint(
            ["voice_session_id", "organization_id", "conversation_id"],
            [
                "voice_sessions.id",
                "voice_sessions.organization_id",
                "voice_sessions.conversation_id",
            ],
            name="fk_voice_segments_session_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "voice_session_id", "sequence", name="uq_voice_segments_session_sequence"
        ),
        UniqueConstraint(
            "message_id",
            name="uq_voice_segments_message_id",
        ),
        Index(
            "ix_voice_segments_org_conversation_created",
            "organization_id",
            "conversation_id",
            "created_at",
        ),
        Index("ix_voice_segments_org_message", "organization_id", "message_id"),
        Index(
            "ix_voice_segments_session_role_type",
            "voice_session_id",
            "role",
            "segment_type",
        ),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[VoiceSegmentRole] = mapped_column(String(32), nullable=False)
    segment_type: Mapped[VoiceSegmentType] = mapped_column(String(32), nullable=False)
    source: Mapped[VoiceSegmentSource] = mapped_column(String(32), nullable=False)
    speech_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    words: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    started_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_track: Mapped[VoiceAudioTrackKind | None] = mapped_column(
        String(32), nullable=True
    )
    audio_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_start_byte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_end_byte: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_input: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tool_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    dtmf_digits: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transfer_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    redaction_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none"
    )
    vendor_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    voice_session: Mapped[VoiceSessionModel] = relationship(back_populates="segments")
