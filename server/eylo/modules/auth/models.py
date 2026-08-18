"""Persistence models for the `auth` domain."""

import secrets

import arrow
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from eylo.common.models import EyloOrganizationModel
from eylo.modules.contacts.constants import APP_DB_PREFIX as CONTACTS_APP_DB_PREFIX

from .constants import APP_DB_PREFIX


class AuthSessionModel(EyloOrganizationModel):
    """Stores a validated session for a contact, typically for a widget.

    A session is created via an authenticated HTTP request and is required
    to establish a WebSocket connection.
    """

    __tablename__ = f"{APP_DB_PREFIX}sessions"

    # The secure token sent to the client.
    session_token = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )

    # Link to the contact this session belongs to.
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CONTACTS_APP_DB_PREFIX}contacts.id"),
        nullable=False,
    )

    # Timestamps for lifecycle management.
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_active_at = Column(
        DateTime(timezone=True), default=arrow.utcnow().datetime, nullable=False
    )

    # Optional security/audit fields.
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            [
                f"{CONTACTS_APP_DB_PREFIX}contacts.id",
                f"{CONTACTS_APP_DB_PREFIX}contacts.organization_id",
            ],
            name="fk_auth_sessions_contact_organization",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_auth_sessions_id_organization",
        ),
        Index(f"ix_{APP_DB_PREFIX}sessions_contact_id", "contact_id"),
    )


class WidgetInvitationModel(EyloOrganizationModel):
    """One opaque, short-lived grant to create a bounded guest chat session."""

    __tablename__ = f"{APP_DB_PREFIX}widget_invitations"

    contact_id = Column(UUID(as_uuid=True), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    agent_revision = Column(Integer, nullable=False)
    token_digest = Column(String(64), nullable=False, unique=True)
    opener = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    issued_by_kind = Column(String(16), nullable=False)
    issued_by_id = Column(UUID(as_uuid=True), nullable=False)
    consumed_request_id = Column(UUID(as_uuid=True), nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True, unique=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True, unique=True)

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            [
                f"{CONTACTS_APP_DB_PREFIX}contacts.id",
                f"{CONTACTS_APP_DB_PREFIX}contacts.organization_id",
            ],
            name="fk_auth_widget_invitations_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_auth_widget_invitations_agent_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            [f"{APP_DB_PREFIX}sessions.id", f"{APP_DB_PREFIX}sessions.organization_id"],
            name="fk_auth_widget_invitations_session_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_auth_widget_invitations_conversation_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "consumed_request_id",
            name="uq_auth_widget_invitations_exchange_request",
        ),
        CheckConstraint(
            "issued_by_kind IN ('member', 'agent')",
            name="ck_auth_widget_invitations_issuer_kind",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_auth_widget_invitations_agent_revision_positive",
        ),
        CheckConstraint(
            "length(btrim(opener)) BETWEEN 1 AND 4096",
            name="ck_auth_widget_invitations_opener_length",
        ),
        CheckConstraint(
            "(consumed_at IS NULL AND consumed_request_id IS NULL "
            "AND session_id IS NULL AND conversation_id IS NULL) OR "
            "(consumed_at IS NOT NULL AND consumed_request_id IS NOT NULL "
            "AND session_id IS NOT NULL AND conversation_id IS NOT NULL)",
            name="ck_auth_widget_invitations_consumption_complete",
        ),
        Index(
            f"ix_{APP_DB_PREFIX}widget_invitations_expires_at",
            "expires_at",
        ),
        Index(
            f"ix_{APP_DB_PREFIX}widget_invitations_contact_id",
            "contact_id",
        ),
    )


class ApiKeyModel(EyloOrganizationModel):
    """Stores API keys for third-party access.

    An API key is only valid for an endpoint that explicitly accepts the API-key
    principal. The raw key is never stored; only a SHA-256 hash is kept for
    validation.
    """

    __tablename__ = f"{APP_DB_PREFIX}api_keys"

    # Label for the key (e.g., "Zapier Integration")
    name = Column(String, nullable=False)

    # Prefix for easier identification and secret scanning (e.g., "eylo_pk_")
    key_prefix = Column(String, nullable=False, index=True)

    # The SHA-256 hash of the full API key.
    hashed_key = Column(String, unique=True, index=True, nullable=False)

    # Status and expiration
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        Index(f"ix_{APP_DB_PREFIX}api_keys_org_id", "organization_id"),
    )
