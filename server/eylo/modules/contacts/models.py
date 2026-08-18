"""Organization-owned contact persistence and lifecycle constraints."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel

from .constants import APP_DB_PREFIX
from .domain import ContactLifecycle


class ContactsModel(EyloOrganizationModel):
    """Canonical contact identity plus an immediate no-new-work fence."""

    __tablename__ = f"{APP_DB_PREFIX}contacts"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name=f"uq_{APP_DB_PREFIX}contacts_id_organization_id",
        ),
        Index(
            f"ix_unqc_{APP_DB_PREFIX}email_org_id",
            "primary_email",
            "organization_id",
            unique=True,
        ),
        Index(
            f"ix_unqc_{APP_DB_PREFIX}phone_org_id",
            "primary_phone",
            "organization_id",
            unique=True,
        ),
        CheckConstraint(
            "primary_email IS NULL OR primary_email = lower(btrim(primary_email))",
            name="ck_contact_contacts_primary_email_canonical",
        ),
        CheckConstraint(
            "primary_phone IS NULL OR primary_phone ~ '^\\+[1-9][0-9]{1,14}$'",
            name="ck_contact_contacts_primary_phone_e164",
        ),
        CheckConstraint(
            "(lifecycle = 'active' AND deletion_requested_at IS NULL) OR "
            "(lifecycle = 'deletion_pending' AND deletion_requested_at IS NOT NULL)",
            name="ck_contact_contacts_lifecycle",
        ),
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferences: Mapped[dict[str, str] | None] = mapped_column(
        JSONB, nullable=True, default=lambda: {}
    )
    lifecycle: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContactLifecycle.ACTIVE.value,
        server_default=ContactLifecycle.ACTIVE.value,
        index=True,
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
