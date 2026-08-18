"""Persistence models for the `agents` domain."""

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

from eylo.common.models import (
    EyloBaseModel,
    EyloOrganizationModel,
    validate_name_and_generate_slug,
)
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability


class AgentStatus(str, Enum):
    """Enum representing the possible statuses of an agent."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentKind(str, Enum):
    """What kind of runtime an agent has.

    Exactly two values, deliberately. The separate-process long-running kind is
    a real concept with no runtime here, and adding the enum value before the
    runtime exists is the honest-surface violation this codebase keeps finding
    — a value an operator can select that does nothing. Add it when it is built.
    """

    CONVERSATIONAL = "CONVERSATIONAL"
    BACKGROUND = "BACKGROUND"


class AgentsModel(EyloOrganizationModel):
    """Model representing an agent in the Eylo platform."""

    __tablename__ = "agent_agents"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_agent_agents_id_organization_id",
        ),
        Index(
            "uq_agent_agents_org_slug_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_agent_agents_published_revision_positive",
        ),
        CheckConstraint(
            "draft_version > 0",
            name="ck_agent_agents_draft_version_positive",
        ),
        CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL "
            "AND draft_dirty = true) OR "
            "(lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_agent_agents_lifecycle_revision",
        ),
        CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_agent_agents_lifecycle",
        ),
        ForeignKeyConstraint(
            ["instruction_template_id", "organization_id"],
            ["definition_templates.id", "definition_templates.organization_id"],
            name="fk_agent_agents_instruction_template_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_agents_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_llm_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["llm_provider_config_id", "llm_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_llm_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["email_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_email_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["email_provider_config_id", "email_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_email_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["webrtc_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_webrtc_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["webrtc_provider_config_id", "webrtc_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_webrtc_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["voice_config_id", "organization_id"],
            ["voice_configs.id", "voice_configs.organization_id"],
            name="fk_agent_agents_voice_config_organization",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["file_upload_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_file_upload_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "file_upload_embedding_provider_config_id",
                "file_upload_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_file_upload_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reranking_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_reranking_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reranking_provider_config_id", "reranking_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_reranking_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "reranking_provider_config_revision IS NULL OR "
            "reranking_provider_config_revision > 0",
            name="ck_agent_agents_reranking_revision_positive",
        ),
        CheckConstraint(
            "reranking_provider_config_revision IS NULL OR "
            "reranking_provider_config_id IS NOT NULL",
            name="ck_agent_agents_reranking_revision_has_config",
        ),
        CheckConstraint(
            "memory_provider_config_revision IS NULL OR "
            "memory_provider_config_revision > 0",
            name="ck_agent_agents_memory_revision_positive",
        ),
        CheckConstraint(
            "memory_provider_config_revision IS NULL OR "
            "memory_provider_config_id IS NOT NULL",
            name="ck_agent_agents_memory_revision_has_config",
        ),
        CheckConstraint(
            "llm_provider_config_revision IS NULL OR "
            "llm_provider_config_revision > 0",
            name="ck_agent_agents_llm_revision_positive",
        ),
        CheckConstraint(
            "llm_provider_config_revision IS NULL OR "
            "llm_provider_config_id IS NOT NULL",
            name="ck_agent_agents_llm_revision_has_config",
        ),
        CheckConstraint(
            "email_provider_config_revision IS NULL OR "
            "email_provider_config_revision > 0",
            name="ck_agent_agents_email_revision_positive",
        ),
        CheckConstraint(
            "email_provider_config_revision IS NULL OR "
            "email_provider_config_id IS NOT NULL",
            name="ck_agent_agents_email_revision_has_config",
        ),
        CheckConstraint(
            "webrtc_provider_config_revision IS NULL OR "
            "webrtc_provider_config_revision > 0",
            name="ck_agent_agents_webrtc_revision_positive",
        ),
        CheckConstraint(
            "webrtc_provider_config_revision IS NULL OR "
            "webrtc_provider_config_id IS NOT NULL",
            name="ck_agent_agents_webrtc_revision_has_config",
        ),
        CheckConstraint(
            "(voice_config_id IS NULL AND voice_config_revision IS NULL) OR "
            "(voice_config_id IS NOT NULL AND voice_config_revision > 0)",
            name="ck_agent_agents_voice_config_ref",
        ),
        CheckConstraint(
            "kind <> 'BACKGROUND' OR "
            "(voice_config_id IS NULL AND voice_config_revision IS NULL)",
            name="ck_agent_agents_background_without_voice_config",
        ),
        CheckConstraint(
            "(allow_file_uploads = false "
            "AND file_upload_embedding_provider_config_id IS NULL "
            "AND file_upload_embedding_provider_config_revision IS NULL) OR "
            "(allow_file_uploads = true "
            "AND file_upload_embedding_provider_config_id IS NOT NULL "
            "AND (file_upload_embedding_provider_config_revision IS NULL OR "
            "file_upload_embedding_provider_config_revision > 0))",
            name="ck_agent_agents_file_upload_configuration",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    llm_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    llm_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    email_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    email_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    webrtc_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    webrtc_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    voice_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    voice_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    llm_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    reranking_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    reranking_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    memory_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    memory_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    allow_file_uploads: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    file_upload_embedding_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    file_upload_embedding_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    instruction_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        ENUM(AgentStatus, name="agent_status_enum"),
        nullable=False,
        default=AgentStatus.DRAFT,
        server_default=AgentStatus.DRAFT,
        doc="Status of the agent.",
    )
    kind: Mapped[AgentKind] = mapped_column(
        ENUM(AgentKind, name="agent_kind_enum"),
        nullable=False,
        default=AgentKind.CONVERSATIONAL,
        server_default=AgentKind.CONVERSATIONAL,
        doc="Whether this agent drives a conversation or runs in the background.",
    )
    implementation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc=(
            "Registry slug naming first-party code for a background agent. "
            "NULL means a generic prompt agent whose output lands as a "
            "TASK_RESULT message and which performs no other side effect."
        ),
    )
    # behaviour
    prompt: Mapped[dict] = mapped_column(
        JSONB, nullable=True, doc="Agent's prompt configuration."
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
        """Validate and generate a slug for the agent name."""
        return validate_name_and_generate_slug(self, key, name)


class AgentRevisionModel(EyloOrganizationModel):
    """Immutable executable agent definition."""

    __tablename__ = "agent_definition_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_agent_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["voice_config_id", "organization_id"],
            ["voice_configs.id", "voice_configs.organization_id"],
            name="fk_agent_definition_revisions_voice_config_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "agent_id",
            "revision",
            name="uq_agent_definition_revisions_ref",
        ),
        UniqueConstraint(
            "agent_id",
            "revision",
            "organization_id",
            name="uq_agent_definition_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_agent_definition_revisions_revision_positive",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_agent_definition_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_definition_revisions_revocation_metadata",
        ),
        CheckConstraint(
            "(instruction_template_id IS NULL AND "
            "instruction_template_revision IS NULL) OR "
            "(instruction_template_id IS NOT NULL AND "
            "instruction_template_revision > 0)",
            name="ck_agent_definition_revisions_template_ref",
        ),
        CheckConstraint(
            "(voice_config_id IS NULL AND voice_config_revision IS NULL "
            "AND voice_config IS NULL) OR "
            "(voice_config_id IS NOT NULL AND voice_config_revision > 0 "
            "AND voice_config IS NOT NULL)",
            name="ck_agent_definition_revisions_voice_config_ref",
        ),
        CheckConstraint(
            "kind <> 'BACKGROUND' OR "
            "(voice_config_id IS NULL AND voice_config_revision IS NULL "
            "AND voice_config IS NULL)",
            name="ck_agent_definition_revisions_background_without_voice_config",
        ),
        ForeignKeyConstraint(
            [
                "instruction_template_id",
                "instruction_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_instruction_template",
            ondelete="RESTRICT",
        ),
        *(
            ForeignKeyConstraint(
                [
                    f"{kind}_provider_config_id",
                    f"{kind}_provider_config_revision",
                    "organization_id",
                ],
                [
                    "provider_config_revisions.provider_config_id",
                    "provider_config_revisions.revision",
                    "provider_config_revisions.organization_id",
                ],
                name=f"fk_agent_definition_revisions_{kind}_provider_config",
                ondelete="RESTRICT",
            )
            for kind in (
                "llm",
                "email",
                "webrtc",
                "reranking",
                "memory",
                "stt",
                "tts",
                "realtime",
                "storage",
            )
        ),
        ForeignKeyConstraint(
            [
                "file_upload_embedding_provider_config_id",
                "file_upload_embedding_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_def_revisions_file_upload_embedding_config",
            ondelete="RESTRICT",
        ),
        *(
            CheckConstraint(
                f"({kind}_provider_config_id IS NULL AND "
                f"{kind}_provider_config_revision IS NULL) OR "
                f"({kind}_provider_config_id IS NOT NULL AND "
                f"{kind}_provider_config_revision > 0)",
                name=f"ck_agent_definition_revisions_{kind}_provider_ref",
            )
            for kind in (
                "email",
                "webrtc",
                "reranking",
                "memory",
                "stt",
                "tts",
                "realtime",
                "storage",
            )
        ),
        CheckConstraint(
            "(allow_file_uploads = false "
            "AND file_upload_embedding_provider_config_id IS NULL "
            "AND file_upload_embedding_provider_config_revision IS NULL) OR "
            "(allow_file_uploads = true "
            "AND file_upload_embedding_provider_config_id IS NOT NULL "
            "AND file_upload_embedding_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_file_upload_configuration",
        ),
        CheckConstraint(
            "llm_provider_config_revision > 0",
            name="ck_agent_definition_revisions_llm_provider_ref",
        ),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    voice_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    instruction_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    instruction_template_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    llm_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    llm_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    email_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    email_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    webrtc_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    webrtc_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    reranking_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reranking_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    memory_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    memory_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    allow_file_uploads: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    file_upload_embedding_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    file_upload_embedding_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    stt_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    stt_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    tts_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    tts_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    realtime_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    realtime_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    storage_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    storage_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    llm_overrides: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    voice_config: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
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


class AgentRevisionToolModel(EyloBaseModel):
    """Exact tool grant copied into one immutable agent revision."""

    __tablename__ = "agent_revision_tools"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    tool_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curated_tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Curated tool granted by this revision. Carries no tool revision "
        "because a curated definition is code, not data.",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    __table_args__ = (
        UniqueConstraint("agent_id", "agent_revision", "tool_id"),
        UniqueConstraint(
            "agent_id",
            "agent_revision",
            "curated_tool_id",
            name="uq_agent_revision_tools_agent_revision_curated_tool",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_tools_agent_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tool_id", "tool_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_tools_tool_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["curated_tool_id", "organization_id"],
            [
                "integration_v2_tools.id",
                "integration_v2_tools.organization_id",
            ],
            name="fk_agent_revision_tools_curated_tool_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "agent_revision > 0 AND (tool_revision IS NULL OR tool_revision > 0)",
            name="ck_agent_revision_tools_revisions_positive",
        ),
        CheckConstraint(
            "(tool_id IS NOT NULL AND tool_revision IS NOT NULL "
            "AND curated_tool_id IS NULL) OR "
            "(tool_id IS NULL AND tool_revision IS NULL "
            "AND curated_tool_id IS NOT NULL)",
            name="ck_agent_revision_tools_exact_tool",
        ),
    )


class AgentRevisionBackgroundAgentModel(EyloBaseModel):
    """Exact enabled background-agent attachment in an agent revision."""

    __tablename__ = "agent_revision_background_agents"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    background_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    background_agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "agent_revision", "background_agent_id"
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_background_agents_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            [
                "background_agent_id",
                "background_agent_revision",
                "organization_id",
            ],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_background_agents_target",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "agent_revision > 0 AND background_agent_revision > 0",
            name="ck_agent_revision_background_agents_revisions_positive",
        ),
        CheckConstraint(
            "agent_id <> background_agent_id",
            name="ck_agent_revision_background_agents_not_self",
        ),
    )


class AgentToolMappingModal(EyloBaseModel):
    """Model representing the mapping between agents and their associated tools."""

    __tablename__ = "agent_tools"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    tool_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curated_tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Curated tool bound to this agent. Curated tools carry no revision "
        "because their definition is code; execution policy is read live.",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id"),
        UniqueConstraint(
            "agent_id",
            "curated_tool_id",
            name="uq_agent_tools_agent_curated_tool",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_agent_tools_agent_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tool_id", "tool_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_agent_tools_tool_revision_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["curated_tool_id", "organization_id"],
            [
                "integration_v2_tools.id",
                "integration_v2_tools.organization_id",
            ],
            name="fk_agent_tools_curated_tool_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tool_revision IS NULL OR tool_revision > 0",
            name="ck_agent_tools_tool_revision_positive",
        ),
        CheckConstraint(
            "(tool_id IS NOT NULL AND tool_revision IS NOT NULL "
            "AND curated_tool_id IS NULL) OR "
            "(tool_id IS NULL AND tool_revision IS NULL "
            "AND curated_tool_id IS NOT NULL)",
            name="ck_agent_tools_exact_tool",
        ),
    )


class AgentBackgroundAgentModel(EyloBaseModel):
    """Attachment of a background agent to a conversational agent."""

    __tablename__ = "agent_background_agents"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The CONVERSATIONAL agent whose run completion triggers dispatch.",
    )
    background_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_agents.id", ondelete="CASCADE"),
        nullable=False,
        doc="The BACKGROUND agent to dispatch.",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (UniqueConstraint("agent_id", "background_agent_id"),)


class AgentSwarmModel(EyloOrganizationModel):
    """Stable swarm identity plus its mutable topology draft."""

    __tablename__ = "agent_swarms"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_agent_swarms_id_organization_id",
        ),
        Index(
            "uq_agent_swarms_org_slug_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_agent_swarms_published_revision_positive",
        ),
        CheckConstraint(
            "draft_version > 0",
            name="ck_agent_swarms_draft_version_positive",
        ),
        CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL "
            "AND draft_dirty = true) OR "
            "(lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_agent_swarms_lifecycle_revision",
        ),
        CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_agent_swarms_lifecycle",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_agent_swarms_published_revision",
            ondelete="RESTRICT",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        """Validate the name and keep the stable draft slug synchronized."""
        return validate_name_and_generate_slug(self, key, name)


class AgentSwarmRevisionModel(EyloOrganizationModel):
    """One immutable published swarm topology."""

    __tablename__ = "agent_swarm_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["swarm_id", "organization_id"],
            ["agent_swarms.id", "agent_swarms.organization_id"],
            name="fk_agent_swarm_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "swarm_id",
            "revision",
            name="uq_agent_swarm_revisions_ref",
        ),
        UniqueConstraint(
            "swarm_id",
            "revision",
            "organization_id",
            name="uq_agent_swarm_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_agent_swarm_revisions_revision_positive",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_agent_swarm_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_swarm_revisions_revocation_metadata",
        ),
    )

    swarm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class AgentSwarmRevisionMemberModel(EyloBaseModel):
    """Exact executable agent member in one immutable swarm topology."""

    __tablename__ = "agent_swarm_revision_members"

    __table_args__ = (
        ForeignKeyConstraint(
            ["swarm_id", "swarm_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_agent_swarm_revision_members_swarm_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_swarm_revision_members_agent_revision",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "swarm_id",
            "swarm_revision",
            "agent_id",
            name="uq_agent_swarm_revision_members_agent",
        ),
        CheckConstraint(
            "swarm_revision > 0 AND agent_revision > 0",
            name="ck_agent_swarm_revision_members_revisions_positive",
        ),
        CheckConstraint(
            "agent_description IS NULL OR "
            "length(agent_description) BETWEEN 1 AND 2000",
            name="ck_agent_swarm_revision_members_description",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    swarm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    swarm_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_description: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentSwarmMappingModel(EyloOrganizationModel):
    """Mutable draft membership for a stable swarm header."""

    __tablename__ = "map_agents_to_swarms"
    __table_args__ = (
        Index(
            "ix_map_agents_to_swarms_agent_swarm",
            "agent_id",
            "swarm_id",
            unique=True,
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_map_agents_to_swarms_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["swarm_id", "organization_id"],
            ["agent_swarms.id", "agent_swarms.organization_id"],
            name="fk_map_agents_to_swarms_swarm_organization",
            ondelete="CASCADE",
        ),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    swarm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    agent_description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        doc="Swarm-specific description for the agent. Overrides agent description if present.",
    )
