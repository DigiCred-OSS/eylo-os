"""Persistence models for the `integrations_v2` domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel

from .constants import APP_DB_PREFIX
from .domain.enums import ToolExecutionMode, VendorAuthKind


class IntegrationV2InstallationModel(EyloOrganizationModel):
    """One organization's installation of one curated vendor."""

    __tablename__ = f"{APP_DB_PREFIX}installations"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_integration_v2_installations_id_organization_id",
        ),
        Index(
            "uq_integration_v2_installations_org_vendor_active",
            "organization_id",
            "vendor",
            unique=True,
            postgresql_where="deleted = false",
        ),
        CheckConstraint(
            "auth_kind IN ('no_auth', 'api_key', 'basic', 'oauth2')",
            name="ck_integration_v2_installations_auth_kind",
        ),
    )

    vendor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Curated registry vendor id, for example 'linear'.",
    )
    auth_kind: Mapped[VendorAuthKind] = mapped_column(
        String(32),
        nullable=False,
        doc="Auth mode this organization chose from the vendor's supported set.",
    )
    instance_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Customer-owned origin for vendors like Atlassian whose host is "
        "per-organization. Null for vendors with a fixed origin.",
    )
    oauth_client_id: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Client id of the organization's own OAuth app for this vendor.",
    )
    oauth_client_secret: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Encrypted client secret. Never returned by any read path.",
    )
    oauth_tenant: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="Directory id for per-tenant providers such as Microsoft.",
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    installed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Member who installed the vendor.",
    )


class IntegrationV2ToolModel(EyloOrganizationModel):
    """One organization's policy for one curated tool.

    Rows are materialized on demand rather than created for every registered
    tool at install time: the id is derived from the organization and wire id,
    so a tool can be bound and policed before any row exists, and a deploy that
    adds tools needs no backfill.
    """

    __tablename__ = f"{APP_DB_PREFIX}tools"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_integration_v2_tools_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["installation_id", "organization_id"],
            [
                f"{IntegrationV2InstallationModel.__tablename__}.id",
                f"{IntegrationV2InstallationModel.__tablename__}.organization_id",
            ],
            name="fk_integration_v2_tools_installation_organization",
            ondelete="CASCADE",
        ),
        Index(
            "uq_integration_v2_tools_org_wire_active",
            "organization_id",
            "wire_id",
            unique=True,
            postgresql_where="deleted = false",
        ),
        CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_integration_v2_tools_execution_mode",
        ),
    )

    installation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    wire_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Registry binding, for example 'linear.list_issues'. The vendor "
        "half is also reachable through installation_id; it is stored here "
        "deliberately so a lookup by binding, and the deterministic row id "
        "derived from it, need no join.",
    )
    execution_mode: Mapped[ToolExecutionMode] = mapped_column(
        String(32),
        nullable=False,
        default=ToolExecutionMode.AUTO.value,
        server_default=ToolExecutionMode.AUTO.value,
    )


__all__ = [
    "IntegrationV2InstallationModel",
    "IntegrationV2ToolModel",
]
