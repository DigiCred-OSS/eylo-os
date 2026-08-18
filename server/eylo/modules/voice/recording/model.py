"""SQLAlchemy model for voice recordings."""

import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.absurd_work import AbsurdBoundWorkMixin
from eylo.common.models import EyloBaseModel


class VoiceRecordingModel(EyloBaseModel, AbsurdBoundWorkMixin):
    """Stores metadata and URLs for voice session recordings.

    Each record represents one voice session's audio capture,
    with separate tracks for user (inbound) and agent (outbound/TTS).
    """

    __tablename__ = "voice_recordings"
    __durable_enum_name__ = "voice_recording_upload_state_enum"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_voice_recordings_id_organization_id",
        ),
        UniqueConstraint(
            "organization_id",
            "session_id",
            name="uq_voice_recordings_organization_session",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_recordings_storage_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "voice_session_id",
                "organization_id",
                "conversation_id",
                "session_id",
            ],
            [
                "voice_sessions.id",
                "voice_sessions.organization_id",
                "voice_sessions.conversation_id",
                "voice_sessions.session_id",
            ],
            name="fk_voice_recordings_session_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "telephony_call_id",
                "organization_id",
                "conversation_id",
                "session_id",
            ],
            [
                "telephony_calls.id",
                "telephony_calls.organization_id",
                "telephony_calls.conversation_id",
                "telephony_calls.call_sid",
            ],
            name="fk_voice_recordings_call_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_voice_recordings_storage_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(storage_provider_config_id IS NULL AND "
            "storage_provider_config_revision IS NULL AND storage_provider IS NULL "
            "AND storage_authority IS NULL AND user_storage_key IS NULL "
            "AND agent_storage_key IS NULL) OR "
            "(storage_provider_config_id IS NOT NULL AND "
            "storage_provider_config_revision IS NOT NULL AND "
            "((storage_provider IS NULL AND storage_authority IS NULL "
            "AND user_storage_key IS NULL AND agent_storage_key IS NULL) OR "
            "(storage_provider IS NOT NULL AND storage_authority IS NOT NULL AND "
            "(user_storage_key IS NOT NULL OR agent_storage_key IS NOT NULL))))",
            name="ck_voice_recordings_storage_locator",
        ),
        CheckConstraint(
            "(staged_user_wav IS NULL OR target_user_storage_key IS NOT NULL) AND "
            "(staged_agent_wav IS NULL OR target_agent_storage_key IS NOT NULL)",
            name="ck_voice_recordings_staged_targets",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    telephony_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    user_audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    storage_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    storage_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    storage_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_authority: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    user_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_user_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_agent_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    staged_user_wav: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    staged_agent_wav: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    user_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    agent_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    user_sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    agent_sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    meta: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc=(
            "Why a recording is not here. A row with null URLs and an "
            "`upload_error` is an attempt that failed — recorded so an "
            "operator looking for missing audio finds the reason next to "
            "where the audio should have been."
        ),
    )
