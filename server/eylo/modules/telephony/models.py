"""Database models for telephony."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel
from eylo.modules.agents.models import AgentsModel
from eylo.modules.telephony.schemas import CallDirection, CallStatus, PhoneNumberStatus

from .constants import APP_DB_PREFIX


class PhoneNumberModel(EyloOrganizationModel):
    __tablename__ = f"{APP_DB_PREFIX}phone_numbers"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["provider_config_id", "provider_config_revision", "organization_id"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_telephony_phone_numbers_provider_config_revision_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "provider_config_revision > 0",
            name="ck_telephony_phone_numbers_provider_config_revision_positive",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'PROVISIONING', "
            "'PROVISIONING_UNKNOWN', 'PROVISIONING_FAILED')",
            name="ck_telephony_phone_numbers_status",
        ),
        CheckConstraint(
            "provisioning_failure_code IS NULL OR "
            "provisioning_failure_code ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_telephony_phone_numbers_failure_code",
        ),
        CheckConstraint(
            "(status = 'PROVISIONING' AND provider_reference IS NULL "
            "AND provisioning_failure_code IS NULL) OR "
            "(status = 'PROVISIONING_UNKNOWN' "
            "AND provisioning_failure_code IS NOT NULL) OR "
            "(status = 'PROVISIONING_FAILED' "
            "AND provisioning_failure_code IS NOT NULL) OR "
            "(status IN ('ACTIVE', 'INACTIVE') "
            "AND provisioning_failure_code IS NULL)",
            name="ck_telephony_phone_numbers_provisioning_state",
        ),
    )

    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[PhoneNumberStatus] = mapped_column(
        String(32), nullable=False, default=PhoneNumberStatus.ACTIVE
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_config_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    provider_config_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_reference: Mapped[Optional[str]] = mapped_column(
        String(320), nullable=True
    )
    provisioning_failure_code: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    inbound_agent_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(AgentsModel.id, ondelete="SET NULL"), nullable=True
    )
    outbound_agent_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(AgentsModel.id, ondelete="SET NULL"), nullable=True
    )


class TelephonyCallModel(EyloOrganizationModel):
    """Persistent record of a telephony call (inbound or outbound)."""

    __tablename__ = f"{APP_DB_PREFIX}calls"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            "call_sid",
            name="uq_telephony_calls_recording_owner",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_telephony_calls_session_owner",
        ),
        ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_telephony_calls_user_session_conversation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_telephony_calls_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_config_id", "provider_config_revision", "organization_id"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_telephony_calls_provider_config_revision_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "provider_config_revision > 0",
            name="ck_telephony_calls_provider_config_revision_positive",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_telephony_calls_agent_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(agent_id IS NULL AND agent_revision IS NULL) OR "
            "(agent_id IS NOT NULL AND agent_revision > 0)",
            name="ck_telephony_calls_agent_ref",
        ),
        CheckConstraint(
            "user_session_id IS NULL OR conversation_id IS NOT NULL",
            name="ck_telephony_calls_user_session_conversation",
        ),
        CheckConstraint(
            "opener_delivery_status IN "
            "('not_requested', 'pending', 'accepted', 'failed')",
            name="ck_telephony_calls_opener_delivery_status",
        ),
        Index(f"ix_{APP_DB_PREFIX}calls_call_sid", "call_sid"),
        Index(f"ix_{APP_DB_PREFIX}calls_conversation_id", "conversation_id"),
        Index(f"ix_{APP_DB_PREFIX}calls_agent_id", "agent_id"),
        Index(f"ix_{APP_DB_PREFIX}calls_status", "status"),
        Index(
            "uq_telephony_calls_campaign_attempt_id",
            "campaign_attempt_id",
            unique=True,
            postgresql_where=text("campaign_attempt_id IS NOT NULL"),
        ),
    )

    call_sid: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, unique=True
    )
    stream_sid: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_config_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    provider_config_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CallDirection.OUTBOUND
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CallStatus.INITIATED
    )

    from_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ended_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    agent_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    user_session_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)
    campaign_contact_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        index=True,
    )
    campaign_attempt_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
    )
    phone_number_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)
    voice_session_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(
            "voice_sessions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_telephony_calls_voice_session_id_voice_sessions",
        ),
        nullable=True,
        index=True,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    media_claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opener_delivery_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_requested",
        server_default="not_requested",
    )
    opener_delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_history: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    recording_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)
    recording_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)
    transcript_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    transfer_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none", server_default="none"
    )
    transfer_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transfer_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    transferred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transfer_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    cost_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    cost_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    latency_metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    provider_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    analysis_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
