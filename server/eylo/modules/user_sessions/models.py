"""Organization-owned persistence for end-user sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloBaseModel, EyloOrganizationModel
from eylo.modules.user_sessions.domain import (
    UserSessionEntryChannel,
    UserSessionState,
)


def _enum(enum_type: type, name: str) -> ENUM:
    return ENUM(
        enum_type,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


class UserSessionModel(EyloOrganizationModel):
    """One channel-neutral end-user visit or call."""

    __tablename__ = "user_sessions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_user_sessions_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_user_sessions_contact_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "connection_sequence >= 1",
            name="ck_user_sessions_connection_sequence",
        ),
        CheckConstraint(
            "end_reason IS NULL OR "
            "(length(end_reason) BETWEEN 1 AND 128 "
            "AND end_reason ~ '^[a-z][a-z0-9_.-]*$')",
            name="ck_user_sessions_end_reason",
        ),
        CheckConstraint(
            "last_activity_at >= started_at AND "
            "(disconnected_at IS NULL OR disconnected_at >= started_at) AND "
            "(ended_at IS NULL OR ended_at >= started_at)",
            name="ck_user_sessions_time_order",
        ),
        CheckConstraint(
            "(state = 'active' AND disconnected_at IS NULL "
            "AND ended_at IS NULL AND end_reason IS NULL) OR "
            "(state = 'disconnected' AND disconnected_at IS NOT NULL "
            "AND ended_at IS NULL AND end_reason IS NULL) OR "
            "(state IN ('ended', 'failed') AND ended_at IS NOT NULL "
            "AND end_reason IS NOT NULL)",
            name="ck_user_sessions_lifecycle",
        ),
        Index(
            "ix_user_sessions_org_started",
            "organization_id",
            "started_at",
        ),
        Index(
            "ix_user_sessions_org_contact_started",
            "organization_id",
            "contact_id",
            "started_at",
        ),
        Index(
            "ix_user_sessions_org_state_activity",
            "organization_id",
            "state",
            "last_activity_at",
        ),
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    entry_channel: Mapped[UserSessionEntryChannel] = mapped_column(
        _enum(UserSessionEntryChannel, "user_session_entry_channel_enum"),
        nullable=False,
    )
    state: Mapped[UserSessionState] = mapped_column(
        _enum(UserSessionState, "user_session_state_enum"),
        nullable=False,
        default=UserSessionState.ACTIVE,
        server_default=UserSessionState.ACTIVE.value,
        index=True,
    )
    connection_sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)


class UserSessionConversationModel(EyloBaseModel):
    """One conversation observed during one user session."""

    __tablename__ = "user_session_conversations"

    __table_args__ = (
        UniqueConstraint(
            "user_session_id",
            "conversation_id",
            name="uq_user_session_conversations_pair",
        ),
        ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_user_session_conversations_session_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_user_session_conversations_conversation_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "last_seen_at >= first_seen_at",
            name="ck_user_session_conversations_time_order",
        ),
        Index(
            "ix_user_session_conversations_org_session",
            "organization_id",
            "user_session_id",
        ),
        Index(
            "ix_user_session_conversations_org_conversation",
            "organization_id",
            "conversation_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
