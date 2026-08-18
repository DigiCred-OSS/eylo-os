"""Persistence for mutable template drafts and immutable published revisions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability
from eylo.modules.templates.domain import TemplateKind


class TemplateModel(EyloOrganizationModel):
    """Stable template identity and its mutable draft."""

    __tablename__ = "definition_templates"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_definition_templates_id_organization_id",
        ),
        Index(
            "uq_definition_templates_org_slug_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_definition_templates_published_revision_positive",
        ),
        CheckConstraint(
            "draft_version > 0",
            name="ck_definition_templates_draft_version_positive",
        ),
        CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL "
            "AND draft_dirty = true) OR "
            "(lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_definition_templates_lifecycle_revision",
        ),
        CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_definition_templates_lifecycle",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_definition_templates_published_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_body: Mapped[str] = mapped_column(Text, nullable=False)
    draft_variable_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
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
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class TemplateRevisionModel(EyloOrganizationModel):
    """Immutable template payload plus emergency-revocation metadata."""

    __tablename__ = "definition_template_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["definition_templates.id", "definition_templates.organization_id"],
            name="fk_definition_template_revisions_template_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "template_id",
            "revision",
            name="uq_definition_template_revisions_template_revision",
        ),
        UniqueConstraint(
            "template_id",
            "revision",
            "organization_id",
            name="uq_definition_template_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_definition_template_revisions_revision_positive",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_definition_template_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_definition_template_revisions_revocation_metadata",
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variable_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    renderer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    availability: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RevisionAvailability.PUBLISHED.value,
        server_default=RevisionAvailability.PUBLISHED.value,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


__all__ = ["TemplateKind", "TemplateModel", "TemplateRevisionModel"]
