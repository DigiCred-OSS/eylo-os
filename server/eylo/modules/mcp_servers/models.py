"""Persistence for MCP server drafts and immutable published revisions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from eylo.common.models import EyloOrganizationModel, validate_name_and_generate_slug
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability


class MCPServerModel(EyloOrganizationModel):
    """Mutable endpoint/header draft for one organization-owned MCP server."""

    __tablename__ = "mcp_servers"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_mcp_servers_id_organization_id",
        ),
        Index(
            "uq_mcp_servers_org_slug_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_mcp_servers_published_revision_positive",
        ),
        CheckConstraint(
            "draft_version > 0",
            name="ck_mcp_servers_draft_version_positive",
        ),
        CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL "
            "AND draft_dirty = true) OR "
            "(lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_mcp_servers_lifecycle_revision",
        ),
        CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_mcp_servers_lifecycle",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "mcp_server_definition_revisions.server_id",
                "mcp_server_definition_revisions.revision",
                "mcp_server_definition_revisions.organization_id",
            ],
            name="fk_mcp_servers_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    discovered_tool_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    lifecycle: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DefinitionLifecycle.DRAFT.value,
        server_default=DefinitionLifecycle.DRAFT.value,
    )
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draft_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    draft_dirty: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    @validates("name")
    def validate_name(self, key, name):
        return validate_name_and_generate_slug(self, key, name)


class MCPServerRevisionModel(EyloOrganizationModel):
    """Immutable endpoint/header envelope selected by exact MCP tool dispatch."""

    __tablename__ = "mcp_server_definition_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["server_id", "organization_id"],
            ["mcp_servers.id", "mcp_servers.organization_id"],
            name="fk_mcp_server_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "server_id",
            "revision",
            name="uq_mcp_server_definition_revisions_ref",
        ),
        UniqueConstraint(
            "server_id",
            "revision",
            "organization_id",
            name="uq_mcp_server_definition_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_mcp_server_definition_revisions_revision_positive",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_mcp_server_definition_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_mcp_server_definition_revisions_revocation_metadata",
        ),
    )

    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    availability: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RevisionAvailability.PUBLISHED.value,
        server_default=RevisionAvailability.PUBLISHED.value,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["MCPServerModel", "MCPServerRevisionModel"]
