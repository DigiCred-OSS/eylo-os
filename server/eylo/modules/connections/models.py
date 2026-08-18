"""Persistence models for the `connections` domain."""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloBaseModel, EyloOrganizationModel
from eylo.modules.connections.constants import APP_DB_PREFIX
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.mappers.enums import ConnectionKind
from eylo.modules.organizations.models import OrganizationModel


class ConnectionStatus(str, Enum):
    """ConnectionStatus behavior for the "connections" domain."""

    INITIATED = "INITIATED"  # connection is initiated
    ACTIVE = "ACTIVE"  # connection is active
    INACTIVE = "INACTIVE"  # connection is not active
    FAILED = "FAILED"  # process failed
    REVOKED = "REVOKED"  # requires authorization again


class ConnectionModel(EyloOrganizationModel):
    """ConnectionModel behavior for the "connections" domain."""

    __tablename__ = f"{APP_DB_PREFIX}connections"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            [
                f"{ContactsModel.__tablename__}.id",
                f"{ContactsModel.__tablename__}.organization_id",
            ],
            name="fk_connection_connections_contact_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["integration_id", "organization_id"],
            [
                "integration_v2_installations.id",
                "integration_v2_installations.organization_id",
            ],
            name="fk_connection_connections_installation_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(connection_kind = 'CONTACT' AND contact_id IS NOT NULL) OR "
            "(connection_kind = 'ORGANIZATION' AND contact_id IS NULL)",
            name="ck_connection_connections_exact_owner",
        ),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Curated vendor installation this connection authorizes.",
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    connection_kind: Mapped[ConnectionKind] = mapped_column(
        ENUM(
            ConnectionKind,
            name="connection_kind_enum",
            create_type=True,
        ),
        nullable=False,
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        ENUM(
            ConnectionStatus,
            name="connection_status_enum",
            create_type=True,
        ),
        nullable=False,
        default=ConnectionStatus.INITIATED,
        server_default=ConnectionStatus.INITIATED,
    )
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=True)
    credentials_expires_at = mapped_column(
        DateTime(
            timezone=True,
        ),
        nullable=True,
        index=True,
    )
    last_refresh_success_at = mapped_column(
        DateTime(
            timezone=True,
        ),
        nullable=True,
        index=True,
    )
    last_refresh_failure_at = mapped_column(
        DateTime(
            timezone=True,
        ),
        nullable=True,
        index=True,
    )
    refresh_attempts = mapped_column(
        SmallInteger,
        server_default="0",
        nullable=False,
    )
    is_refresh_exhausted = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
    )


class OAuthStateModel(EyloBaseModel):
    """Tracks OAuth authorization state tokens.

    This model stores temporary state tokens used during OAuth flows to prevent
    CSRF attacks and track authorization requests.
    """

    __tablename__ = f"{APP_DB_PREFIX}oauth_states"

    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Unique state token for OAuth flow",
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Curated vendor installation this flow authorizes.",
    )

    code_verifier: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment=(
            "PKCE code verifier held for the token exchange. Null for providers "
            "that do not use PKCE. Never leaves the server: only its S256 "
            "challenge is sent to the authorization endpoint."
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{OrganizationModel.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization initiating the OAuth flow",
    )

    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Optional contact to associate with resulting connection",
    )

    redirect_uri: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Custom redirect URI for this flow",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this state token expires",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            [
                f"{ContactsModel.__tablename__}.id",
                f"{ContactsModel.__tablename__}.organization_id",
            ],
            name="fk_connection_oauth_states_contact_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["integration_id", "organization_id"],
            [
                "integration_v2_installations.id",
                "integration_v2_installations.organization_id",
            ],
            name="fk_connection_oauth_states_installation_organization",
            ondelete="CASCADE",
        ),
        Index("ix_oauth_states_expires_at", expires_at),
        Index("ix_oauth_states_state", state, unique=True),
    )

    @staticmethod
    def generate_state_token() -> str:
        """Generate a secure random state token."""
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64 characters

    @staticmethod
    def calculate_expiry(minutes: int = 10) -> datetime:
        """Calculate expiry timestamp.

        Args:
            minutes: Minutes until expiration (default: 10)

        Returns:
            Datetime of expiration

        """
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def is_expired(self) -> bool:
        """Check if this state token has expired.

        Returns:
            True if expired, False otherwise

        """
        return datetime.now(timezone.utc) > self.expires_at
