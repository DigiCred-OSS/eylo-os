"""Persistence and domain vocabulary for platform-owned executable tools."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from eylo.common.models import EyloOrganizationModel, validate_name_and_generate_slug
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability


class ToolKind(str, Enum):
    """Execution boundary for a tool exposed to an agent."""

    LOCAL = "LOCAL"
    SYSTEM = "SYSTEM"
    MCP = "MCP"
    CURATED = "CURATED"


class ToolExecutionMode(str, Enum):
    """Persisted policy controlling whether an exact tool may execute."""

    AUTO = "auto"
    REQUIRES_APPROVAL = "requires_approval"
    DISABLED = "disabled"


class ToolModel(EyloOrganizationModel):
    """Mutable header for platform and discovered MCP tools.

    Curated vendor tools do not use this table. Their contracts live in the V2
    registry and their organization policy lives in `integration_v2_tools`.
    """

    __tablename__ = "platform_tools"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_platform_tools_id_organization_id",
        ),
        Index(
            "uq_platform_tools_org_slug_unbound_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text(
                "mcp_server_id IS NULL AND deleted = false"
            ),
        ),
        Index(
            "uq_platform_tools_mcp_wire_active",
            "mcp_server_id",
            "wire_id",
            unique=True,
            postgresql_where=text(
                "mcp_server_id IS NOT NULL AND wire_id IS NOT NULL "
                "AND deleted = false"
            ),
        ),
        CheckConstraint(
            "kind IN ('LOCAL', 'SYSTEM', 'MCP')",
            name="ck_platform_tools_persisted_kind",
        ),
        CheckConstraint(
            "(kind = 'MCP' AND mcp_server_id IS NOT NULL "
            "AND wire_id IS NOT NULL) OR "
            "(kind <> 'MCP' AND mcp_server_id IS NULL AND wire_id IS NULL)",
            name="ck_platform_tools_exact_mcp_owner",
        ),
        CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_platform_tools_published_revision_positive",
        ),
        CheckConstraint(
            "draft_version > 0",
            name="ck_platform_tools_draft_version_positive",
        ),
        CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL "
            "AND draft_dirty = true) OR "
            "(lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_platform_tools_lifecycle_revision",
        ),
        CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_platform_tools_lifecycle",
        ),
        CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_platform_tools_execution_mode",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_platform_tools_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[ToolKind] = mapped_column(
        ENUM(ToolKind, name="tool_kind_enum"),
        nullable=False,
        doc="Persisted tools are LOCAL, SYSTEM, or MCP.",
    )
    display_name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    llm_config: Mapped[dict | None] = mapped_column(JSONB)
    executor_config: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    execution_mode: Mapped[ToolExecutionMode] = mapped_column(
        String(32),
        nullable=False,
        default=ToolExecutionMode.AUTO.value,
        server_default=ToolExecutionMode.AUTO.value,
    )
    wire_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
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


class ToolRevisionModel(EyloOrganizationModel):
    """Immutable platform/MCP tool payload selected by exact dispatch."""

    __tablename__ = "tool_definition_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["tool_id", "organization_id"],
            ["platform_tools.id", "platform_tools.organization_id"],
            name="fk_tool_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["mcp_server_id", "mcp_server_revision", "organization_id"],
            [
                "mcp_server_definition_revisions.server_id",
                "mcp_server_definition_revisions.revision",
                "mcp_server_definition_revisions.organization_id",
            ],
            name="fk_tool_definition_revisions_mcp_server_revision",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tool_id",
            "revision",
            name="uq_tool_definition_revisions_ref",
        ),
        UniqueConstraint(
            "tool_id",
            "revision",
            "organization_id",
            name="uq_tool_definition_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_tool_definition_revisions_revision_positive",
        ),
        CheckConstraint(
            "(kind = 'MCP' AND mcp_server_id IS NOT NULL "
            "AND mcp_server_revision IS NOT NULL AND wire_id IS NOT NULL) OR "
            "(kind <> 'MCP' AND mcp_server_id IS NULL "
            "AND mcp_server_revision IS NULL AND wire_id IS NULL)",
            name="ck_tool_definition_revisions_exact_mcp_owner",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_tool_definition_revisions_availability",
        ),
        CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_tool_definition_revisions_execution_mode",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_tool_definition_revisions_revocation_metadata",
        ),
    )

    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    executor_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    execution_mode: Mapped[ToolExecutionMode] = mapped_column(
        String(32),
        nullable=False,
        default=ToolExecutionMode.AUTO.value,
        server_default=ToolExecutionMode.AUTO.value,
    )
    wire_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    mcp_server_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
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
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = [
    "ToolExecutionMode",
    "ToolKind",
    "ToolModel",
    "ToolRevisionModel",
]
