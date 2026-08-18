"""Database models for the campaigns module."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from eylo.absurd_work import AbsurdBoundWorkMixin
from eylo.common.models import EyloOrganizationModel
from eylo.common.revisions import RevisionAvailability
from eylo.products.campaigns.constants import (
    APP_DB_PREFIX,
    CampaignChannel,
    CampaignContactStatus,
    CampaignStatus,
)


class CampaignModel(EyloOrganizationModel):
    """Stable campaign identity, latest definition, and execution state.

    Attributes:
        name: Human-readable campaign name.
        description: Optional internal notes.
        status: Lifecycle state (draft → running → completed).
        channel: Outreach channel — voice, email, or widget.
        channel_config: JSONB with channel-specific settings.
        agent_id/agent_revision: Exact AI agent definition for new outreach.
        initial_message_template_id/revision: Exact campaign message template.
        schedule_config: JSONB with time_window_start/end, timezone.
        retry_policy: JSONB with max_retries, backoff_seconds, retry_on reasons.
        concurrency_limit: Max simultaneous active outreach items.
        total_contacts: Denormalized count of campaign_contacts rows.
        completed_contacts: Contacts that reached terminal state.
        failed_contacts: Contacts that exhausted retries.
        started_at: When the campaign transitioned to RUNNING.
        completed_at: When all contacts reached terminal state.

    """

    __tablename__ = f"{APP_DB_PREFIX}campaigns"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_campaign_campaigns_id_organization_id",
        ),
        CheckConstraint(
            "published_revision > 0",
            name="ck_campaign_campaigns_published_revision_positive",
        ),
        CheckConstraint(
            "active_revision IS NULL OR active_revision > 0",
            name="ck_campaign_campaigns_active_revision_positive",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_campaign_campaigns_agent_revision_positive",
        ),
        CheckConstraint(
            "(initial_message_template_id IS NULL AND "
            "initial_message_template_revision IS NULL) OR "
            "(initial_message_template_id IS NOT NULL AND "
            "initial_message_template_revision > 0)",
            name="ck_campaign_campaigns_template_ref",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_published_revision",
            # NO ACTION preserves the reference at commit while allowing this
            # header/revision cycle to be removed in one deferred transaction.
            ondelete="NO ACTION",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["id", "active_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_active_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_agent_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "initial_message_template_id",
                "initial_message_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_template_revision",
            ondelete="RESTRICT",
        ),
        Index(f"ix_{APP_DB_PREFIX}campaigns_status", "status"),
        Index(f"ix_{APP_DB_PREFIX}campaigns_agent_id", "agent_id"),
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CampaignStatus.DRAFT
    )

    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=CampaignChannel.VOICE.value
    )
    channel_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    published_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    active_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    agent_id: Mapped[UUID] = mapped_column(nullable=False)
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_message_template_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
    )
    initial_message_template_revision: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    schedule_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    retry_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    concurrency_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )

    total_contacts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    completed_contacts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    failed_contacts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CampaignRevisionModel(EyloOrganizationModel):
    """One immutable campaign definition used by activation and attempts."""

    __tablename__ = "campaign_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_campaign_revisions_agent_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "initial_message_template_id",
                "initial_message_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_campaign_revisions_template_revision",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "campaign_id",
            "revision",
            name="uq_campaign_revisions_ref",
        ),
        UniqueConstraint(
            "campaign_id",
            "revision",
            "organization_id",
            name="uq_campaign_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0 AND agent_revision > 0",
            name="ck_campaign_revisions_revisions_positive",
        ),
        CheckConstraint(
            "(initial_message_template_id IS NULL AND "
            "initial_message_template_revision IS NULL) OR "
            "(initial_message_template_id IS NOT NULL AND "
            "initial_message_template_revision > 0)",
            name="ck_campaign_revisions_template_ref",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_campaign_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_campaign_revisions_revocation_metadata",
        ),
    )

    campaign_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    agent_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_message_template_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    initial_message_template_revision: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    schedule_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    retry_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    availability: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RevisionAvailability.PUBLISHED.value,
        server_default=RevisionAvailability.PUBLISHED.value,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    published_by: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CampaignContactModel(EyloOrganizationModel):
    """A contact linked to a campaign with per-campaign execution state."""

    __tablename__ = f"{APP_DB_PREFIX}contacts"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_contacts_campaign_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_campaign_contacts_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "campaign_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_contacts_campaign_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "campaign_revision IS NULL OR campaign_revision > 0",
            name="ck_campaign_contacts_campaign_revision_positive",
        ),
        UniqueConstraint(
            "campaign_id",
            "contact_address",
            name=f"uq_{APP_DB_PREFIX}contacts_campaign_address",
        ),
        UniqueConstraint(
            "id",
            "campaign_id",
            "organization_id",
            name="uq_campaign_contacts_id_campaign_organization",
        ),
        Index(f"ix_{APP_DB_PREFIX}contacts_campaign_id", "campaign_id"),
        Index(f"ix_{APP_DB_PREFIX}contacts_status", "status"),
        Index(
            f"ix_{APP_DB_PREFIX}contacts_retry",
            "campaign_id",
            "status",
            "next_retry_at",
        ),
    )

    campaign_id: Mapped[UUID] = mapped_column(nullable=False)
    campaign_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contact_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    contact_address: Mapped[str] = mapped_column(String(256), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CampaignContactStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_tracking_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    last_outcome_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    variables: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class CampaignAttemptModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One durably dispatched provider effect for one campaign contact."""

    __tablename__ = "campaign_attempts"
    __durable_enum_name__ = "campaign_attempt_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_attempts_campaign_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "campaign_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_attempts_campaign_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["campaign_contact_id", "campaign_id", "organization_id"],
            [
                "campaign_contacts.id",
                "campaign_contacts.campaign_id",
                "campaign_contacts.organization_id",
            ],
            name="fk_campaign_attempts_contact_campaign_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "campaign_contact_id",
            "attempt_number",
            name="uq_campaign_attempts_contact_number",
        ),
        CheckConstraint(
            "campaign_revision > 0 AND attempt_number > 0",
            name="ck_campaign_attempts_revisions_positive",
        ),
        CheckConstraint(
            "effect_completed_at IS NULL OR effect_started_at IS NOT NULL",
            name="ck_campaign_attempts_effect_order",
        ),
        CheckConstraint(
            "(outcome IS NULL AND outcome_recorded_at IS NULL) OR "
            "(outcome IS NOT NULL AND outcome_recorded_at IS NOT NULL)",
            name="ck_campaign_attempts_outcome_pair",
        ),
        CheckConstraint(
            "dispatch_unknown IS FALSE OR "
            "(effect_started_at IS NOT NULL AND effect_completed_at IS NULL)",
            name="ck_campaign_attempts_unknown_effect",
        ),
        Index(
            "ix_campaign_attempts_campaign_state",
            "campaign_id",
            "state",
        ),
        Index(
            "ix_campaign_attempts_contact_tracking",
            "campaign_contact_id",
            "tracking_id",
        ),
    )

    campaign_id: Mapped[UUID] = mapped_column(nullable=False)
    campaign_contact_id: Mapped[UUID] = mapped_column(nullable=False)
    campaign_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    effect_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    effect_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    effect_replay_safe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dispatch_unknown: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    tracking_id: Mapped[str | None] = mapped_column(String(320), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
