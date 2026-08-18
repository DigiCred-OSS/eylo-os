"""Typed-owner facts, attributable changes, and durable formation."""

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.absurd_work import AbsurdBoundWorkMixin
from eylo.common.contracts.memory import MemoryEvent, MemoryLevel
from eylo.common.contracts.memory_reconciliation import MemoryRelationshipKind
from eylo.common.models import EyloBaseModel, EyloOrganizationModel
from eylo.common.sql_types import VectorType
from eylo.modules.memory.reindex import MemoryReindexState


class MemoryModel(EyloOrganizationModel):
    """One fact owned by one organization Agent, User, or Conversation."""

    __tablename__ = "memory_memories"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "conversation_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_conversation_content_config",
        ),
        UniqueConstraint(
            "organization_id",
            "agent_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_agent_content_config",
        ),
        UniqueConstraint(
            "organization_id",
            "contact_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_contact_content_config",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_memories_id_organization_id",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_memories_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_memories_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_memories_contact_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(scope_level = 'agent' AND agent_id IS NOT NULL AND "
            "contact_id IS NULL AND conversation_id IS NULL) OR "
            "(scope_level = 'user' AND contact_id IS NOT NULL AND "
            "agent_id IS NULL AND conversation_id IS NULL) OR "
            "(scope_level = 'conversation' AND conversation_id IS NOT NULL AND "
            "agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_memories_exact_scope_owner",
        ),
        CheckConstraint(
            "state_revision > 0 AND reconciled_state_revision >= 0 "
            "AND reconciled_state_revision <= state_revision",
            name="ck_memory_memories_reconciliation_revision",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memories_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memories_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memories_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memories_embedding_config_revision",
            ondelete="RESTRICT",
        ),
    )

    scope_level: Mapped[MemoryLevel] = mapped_column(
        ENUM(
            MemoryLevel,
            name="memory_level_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # Provenance only: it deliberately has no FK. Source deletion must not
    # transfer lifecycle control away from the Agent/User/Conversation owner.
    source_conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    reconciled_state_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    recall_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_recalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[str | None] = mapped_column(VectorType(), nullable=True)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )


class MemoryIndexModel(EyloOrganizationModel):
    """Active and staged vector authority for one stable Memory config."""

    __tablename__ = "memory_indexes"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_indexes_id_organization_id",
        ),
        UniqueConstraint(
            "memory_provider_config_id",
            "organization_id",
            name="uq_memory_indexes_config_organization",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_memory_config_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_indexes_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_target_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_indexes_target_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(reindex_state = 'active' "
            "AND target_embedding_provider_config_id IS NULL "
            "AND target_embedding_provider_config_revision IS NULL "
            "AND target_embedding_provider IS NULL "
            "AND target_embedding_endpoint IS NULL "
            "AND target_embedding_model IS NULL "
            "AND target_embedding_dimensions IS NULL "
            "AND target_embedding_semantic_options IS NULL "
            "AND target_embedding_space_id IS NULL "
            "AND reindex_last_error IS NULL) OR "
            "(reindex_state <> 'active' "
            "AND target_embedding_provider_config_id IS NOT NULL "
            "AND target_embedding_provider_config_revision IS NOT NULL "
            "AND target_embedding_provider IS NOT NULL "
            "AND target_embedding_endpoint IS NOT NULL "
            "AND target_embedding_model IS NOT NULL "
            "AND target_embedding_dimensions IS NOT NULL "
            "AND target_embedding_semantic_options IS NOT NULL "
            "AND target_embedding_space_id IS NOT NULL "
            "AND target_embedding_space_id <> embedding_space_id "
            "AND ((reindex_state = 'failed' AND reindex_last_error IS NOT NULL) "
            "OR (reindex_state <> 'failed' AND reindex_last_error IS NULL)))",
            name="ck_memory_indexes_reindex_state",
        ),
    )

    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    reindex_state: Mapped[MemoryReindexState] = mapped_column(
        ENUM(
            MemoryReindexState,
            name="memory_reindex_state_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=MemoryReindexState.ACTIVE,
        server_default=MemoryReindexState.ACTIVE.value,
    )
    target_embedding_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    target_embedding_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    target_embedding_provider: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    target_embedding_endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_embedding_model: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    target_embedding_dimensions: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    target_embedding_semantic_options: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    target_embedding_space_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    reindex_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MemoryReindexJobModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One immutable Memory source-space to target-space transition."""

    __tablename__ = "memory_reindex_jobs"
    __durable_enum_name__ = "memory_reindex_job_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_reindex_jobs_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_memory_config_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_source_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "source_embedding_provider_config_id",
                "source_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reindex_jobs_source_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_target_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reindex_jobs_target_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_embedding_space_id <> target_embedding_space_id",
            name="ck_memory_reindex_jobs_distinct_spaces",
        ),
        Index(
            "uq_memory_reindex_jobs_active_config",
            "memory_provider_config_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
    )

    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    source_embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    source_embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    source_embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    source_embedding_semantic_options: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )
    source_embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    target_embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    target_embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    target_embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    target_embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    target_embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    target_embedding_semantic_options: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )
    target_embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    source_fact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    indexed_fact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


class MemoryReindexVectorModel(EyloOrganizationModel):
    """Staged target vector fenced to one fact state revision."""

    __tablename__ = "memory_reindex_vectors"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["reindex_job_id", "organization_id"],
            ["memory_reindex_jobs.id", "memory_reindex_jobs.organization_id"],
            name="fk_memory_reindex_vectors_job_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_reindex_vectors_memory_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "reindex_job_id",
            "memory_id",
            name="uq_memory_reindex_vectors_job_memory",
        ),
        CheckConstraint(
            "source_state_revision > 0",
            name="ck_memory_reindex_vectors_state_revision_positive",
        ),
    )

    reindex_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[str] = mapped_column(VectorType(), nullable=False)


class MemoryChangeModel(EyloBaseModel):
    """Append-only record of what happened to a memory.

    No foreign key points to the fact row: a content-free deletion event can
    survive current-row deletion. The owning conversation remains explicit;
    the later data-control workflow clears prior content before deleting that
    conversation.
    """

    __tablename__ = "memory_changes"

    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_changes_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_changes_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_changes_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_reconciliation_llm_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_reconciliation_llm_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(scope_level = 'agent' AND agent_id IS NOT NULL AND "
            "contact_id IS NULL AND conversation_id IS NULL) OR "
            "(scope_level = 'user' AND contact_id IS NOT NULL AND "
            "agent_id IS NULL AND conversation_id IS NULL) OR "
            "(scope_level = 'conversation' AND conversation_id IS NOT NULL AND "
            "agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_changes_exact_scope_owner",
        ),
        CheckConstraint(
            "(formation_job_id IS NULL AND formation_operation_index IS NULL) OR "
            "(formation_job_id IS NOT NULL AND formation_operation_index IS NOT NULL)",
            name="ck_memory_changes_formation_operation",
        ),
        CheckConstraint(
            "(reconciliation_job_id IS NULL AND "
            "reconciliation_operation_index IS NULL) OR "
            "(reconciliation_job_id IS NOT NULL AND "
            "reconciliation_operation_index IS NOT NULL)",
            name="ck_memory_changes_reconciliation_operation",
        ),
        CheckConstraint(
            "memory_state_revision > 0 AND embedding_dimensions > 0",
            name="ck_memory_changes_authority_positive",
        ),
        UniqueConstraint(
            "formation_job_id",
            "formation_operation_index",
            name="uq_memory_changes_formation_operation",
        ),
        UniqueConstraint(
            "reconciliation_job_id",
            "reconciliation_operation_index",
            name="uq_memory_changes_reconciliation_operation",
        ),
    )

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scope_level: Mapped[MemoryLevel] = mapped_column(
        ENUM(
            MemoryLevel,
            name="memory_level_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # Content-free source identity survives source-record erasure for audit.
    source_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    event: Mapped[MemoryEvent] = mapped_column(
        ENUM(
            MemoryEvent,
            name="memory_event_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
    )
    before: Mapped[str | None] = mapped_column(Text, nullable=True)
    after: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    memory_state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    reconciliation_llm_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    reconciliation_llm_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    reconciliation_llm_provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    reconciliation_llm_model: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    reconciliation_prompt_revision: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    formation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    formation_operation_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    reconciliation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    reconciliation_operation_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )


class MemoryReconciliationJobModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One immutable changed-fact range for an exact Memory partition."""

    __tablename__ = "memory_reconciliation_jobs"
    __durable_enum_name__ = "memory_reconciliation_job_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_reconciliation_jobs_id_organization",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_reconciliation_jobs_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_reconciliation_jobs_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_reconciliation_jobs_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_llm_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_llm_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND "
            "agent_id IS NOT NULL AND contact_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'user' AND owner_id = contact_id AND "
            "contact_id IS NOT NULL AND agent_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'conversation' AND owner_id = conversation_id AND "
            "conversation_id IS NOT NULL AND agent_id IS NULL AND "
            "contact_id IS NULL)",
            name="ck_memory_reconciliation_jobs_exact_owner",
        ),
        CheckConstraint(
            "generation > 0 AND change_count BETWEEN 1 AND 20",
            name="ck_memory_reconciliation_jobs_generation_count",
        ),
        CheckConstraint(
            "(range_start_created_at IS NULL AND range_start_change_id IS NULL) OR "
            "(range_start_created_at IS NOT NULL AND range_start_change_id IS NOT NULL)",
            name="ck_memory_reconciliation_jobs_range_start_pair",
        ),
        CheckConstraint(
            "range_start_created_at IS NULL OR "
            "ROW(range_through_created_at, range_through_change_id) > "
            "ROW(range_start_created_at, range_start_change_id)",
            name="ck_memory_reconciliation_jobs_range_advances",
        ),
        CheckConstraint(
            "embedding_dimensions > 0 AND considered_count >= 0 AND "
            "duplicate_count >= 0 AND superseded_count >= 0 AND "
            "conflict_count >= 0 AND unrelated_count >= 0 AND failed_count >= 0",
            name="ck_memory_reconciliation_jobs_counts_nonnegative",
        ),
        CheckConstraint(
            "considered_count = duplicate_count + superseded_count + "
            "conflict_count + unrelated_count + failed_count",
            name="ck_memory_reconciliation_jobs_outcome_partition",
        ),
        Index(
            "uq_memory_reconciliation_jobs_active_partition",
            "organization_id",
            "memory_provider_config_id",
            "scope_level",
            "owner_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
    )

    scope_level: Mapped[MemoryLevel] = mapped_column(
        ENUM(
            MemoryLevel,
            name="memory_level_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    range_start_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    range_start_change_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    range_through_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    range_through_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    change_count: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    reconciliation_llm_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    reconciliation_llm_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    reconciliation_llm_provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    reconciliation_llm_model: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    reconciliation_prompt_revision: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    considered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    superseded_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    conflict_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    unrelated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


class MemoryReconciliationCursorModel(EyloOrganizationModel):
    """Requested and processed Memory-change watermarks for one partition."""

    __tablename__ = "memory_reconciliation_cursors"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "organization_id",
            "memory_provider_config_id",
            "scope_level",
            "owner_id",
            name="uq_memory_reconciliation_cursors_partition",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_reconciliation_cursors_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_reconciliation_cursors_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_reconciliation_cursors_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_llm_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_llm_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["active_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_reconciliation_cursors_active_job_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND "
            "agent_id IS NOT NULL AND contact_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'user' AND owner_id = contact_id AND "
            "contact_id IS NOT NULL AND agent_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'conversation' AND owner_id = conversation_id AND "
            "conversation_id IS NOT NULL AND agent_id IS NULL AND "
            "contact_id IS NULL)",
            name="ck_memory_reconciliation_cursors_exact_owner",
        ),
        CheckConstraint(
            "(processed_through_created_at IS NULL AND "
            "processed_through_change_id IS NULL) OR "
            "(processed_through_created_at IS NOT NULL AND "
            "processed_through_change_id IS NOT NULL)",
            name="ck_memory_reconciliation_cursors_processed_pair",
        ),
        CheckConstraint(
            "processed_through_created_at IS NULL OR "
            "ROW(requested_through_created_at, requested_through_change_id) >= "
            "ROW(processed_through_created_at, processed_through_change_id)",
            name="ck_memory_reconciliation_cursors_watermark_order",
        ),
        CheckConstraint(
            "next_generation > 0 AND embedding_dimensions > 0",
            name="ck_memory_reconciliation_cursors_positive",
        ),
    )

    scope_level: Mapped[MemoryLevel] = mapped_column(
        ENUM(
            MemoryLevel,
            name="memory_level_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    reconciliation_llm_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    reconciliation_llm_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    reconciliation_llm_provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    reconciliation_llm_model: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    reconciliation_prompt_revision: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    requested_through_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    requested_through_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    processed_through_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_through_change_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    active_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    next_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class MemoryReconciliationEffectModel(EyloOrganizationModel):
    """Immutable reconciliation evidence, proposal, and atomic outcome."""

    __tablename__ = "memory_reconciliation_effects"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_reconciliation_effects_job_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "reconciliation_job_id",
            name="uq_memory_reconciliation_effects_job",
        ),
    )

    reconciliation_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    outcomes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MemoryRelationshipModel(EyloOrganizationModel):
    """One revision-fenced duplicate, supersession, or conflict decision."""

    __tablename__ = "memory_relationships"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["source_memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_relationships_source_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_relationships_target_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_relationships_job_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_relationships_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_relationships_agent_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_relationships_contact_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_relationships_conversation_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_memory_id <> target_memory_id AND "
            "source_state_revision > 0 AND target_state_revision > 0 AND "
            "jsonb_array_length(evidence_change_ids) > 0",
            name="ck_memory_relationships_exact_evidence",
        ),
        CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND "
            "agent_id IS NOT NULL AND contact_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'user' AND owner_id = contact_id AND "
            "contact_id IS NOT NULL AND agent_id IS NULL AND "
            "conversation_id IS NULL) OR "
            "(scope_level = 'conversation' AND owner_id = conversation_id AND "
            "conversation_id IS NOT NULL AND agent_id IS NULL AND "
            "contact_id IS NULL)",
            name="ck_memory_relationships_exact_owner",
        ),
        UniqueConstraint(
            "reconciliation_job_id",
            "source_memory_id",
            "target_memory_id",
            "kind",
            name="uq_memory_relationships_job_pair_kind",
        ),
    )

    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    scope_level: Mapped[MemoryLevel] = mapped_column(
        ENUM(
            MemoryLevel,
            name="memory_level_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    kind: Mapped[MemoryRelationshipKind] = mapped_column(
        ENUM(
            MemoryRelationshipKind,
            name="memory_relationship_kind_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    source_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    target_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciliation_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    evidence_change_ids: Mapped[list] = mapped_column(JSONB, nullable=False)


class MemoryFormationJobModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One immutable, bounded conversation range waiting to be learned from.

    Formation is an LLM call, so it happens on the shared Absurd worker rather
    than on the turn. The row owns product state and exact config authority;
    Absurd owns execution retries. `MemoryFormationEffectModel` stores one
    fully validated operation plan and its atomic outcome for replay.

    A conversation has at most one pending/running generation. New messages
    only advance its cursor request; successor generations page the remaining
    range after the active generation commits its processed watermark.
    """

    __tablename__ = "memory_formation_jobs"
    __durable_enum_name__ = "memory_formation_state_enum"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_formation_jobs_id_organization",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_memory_formation_jobs_id_owner",
        ),
        UniqueConstraint(
            "organization_id",
            "conversation_id",
            "generation",
            name="uq_memory_formation_jobs_generation",
        ),
        Index(
            "ix_memory_formation_jobs_one_active",
            "organization_id",
            "conversation_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_jobs_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "embedding_provider_config_id",
                "embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["extraction_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_extraction_llm_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "extraction_llm_provider_config_id",
                "extraction_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_extraction_llm_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "generation > 0 AND message_count BETWEEN 1 AND 20",
            name="ck_memory_jobs_generation_count",
        ),
        CheckConstraint(
            "(range_start_created_at IS NULL AND range_start_message_id IS NULL) OR "
            "(range_start_created_at IS NOT NULL AND "
            "range_start_message_id IS NOT NULL)",
            name="ck_memory_jobs_range_start_pair",
        ),
        CheckConstraint(
            "range_through_created_at IS NOT NULL AND "
            "range_through_message_id IS NOT NULL",
            name="ck_memory_jobs_range_through_pair",
        ),
        CheckConstraint(
            "range_start_created_at IS NULL OR "
            "ROW(range_through_created_at, range_through_message_id) > "
            "ROW(range_start_created_at, range_start_message_id)",
            name="ck_memory_jobs_range_advances",
        ),
        CheckConstraint(
            "considered_count >= 0 AND added_count >= 0 AND "
            "updated_count >= 0 AND deleted_count >= 0 AND "
            "noop_count >= 0 AND failed_count >= 0",
            name="ck_memory_jobs_outcome_counts_nonnegative",
        ),
        CheckConstraint(
            "considered_count = added_count + updated_count + deleted_count + "
            "noop_count + failed_count",
            name="ck_memory_jobs_outcome_partition",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    range_start_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    range_start_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    range_through_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    range_through_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    message_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    embedding_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_semantic_options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    extraction_llm_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    extraction_llm_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    extraction_llm_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_llm_model: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_prompt_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    considered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    added_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    deleted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    noop_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


class MemoryFormationCursorModel(EyloOrganizationModel):
    """Monotonic conversation watermark and one active formation generation."""

    __tablename__ = "memory_formation_cursors"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "conversation_id",
            name="uq_memory_formation_cursors_conversation",
        ),
        UniqueConstraint(
            "active_job_id",
            name="uq_memory_formation_cursors_active_job",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_cursors_conversation_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_cursors_memory_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_cursors_memory_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["active_job_id", "organization_id", "conversation_id"],
            [
                "memory_formation_jobs.id",
                "memory_formation_jobs.organization_id",
                "memory_formation_jobs.conversation_id",
            ],
            name="fk_memory_cursors_active_job_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "next_generation > 0",
            name="ck_memory_cursors_next_generation_positive",
        ),
        CheckConstraint(
            "(processed_through_created_at IS NULL AND "
            "processed_through_message_id IS NULL) OR "
            "(processed_through_created_at IS NOT NULL AND "
            "processed_through_message_id IS NOT NULL)",
            name="ck_memory_cursors_processed_pair",
        ),
        CheckConstraint(
            "(requested_through_created_at IS NULL AND "
            "requested_through_message_id IS NULL) OR "
            "(requested_through_created_at IS NOT NULL AND "
            "requested_through_message_id IS NOT NULL)",
            name="ck_memory_cursors_requested_pair",
        ),
        CheckConstraint(
            "processed_through_created_at IS NULL OR "
            "(requested_through_created_at IS NOT NULL AND "
            "ROW(requested_through_created_at, requested_through_message_id) >= "
            "ROW(processed_through_created_at, processed_through_message_id))",
            name="ck_memory_cursors_requested_covers_processed",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    memory_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    processed_through_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_through_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    requested_through_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_through_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    active_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    next_generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )


class MemoryFormationEffectModel(EyloOrganizationModel):
    """Immutable plan plus one all-or-nothing outcome for a formation job."""

    __tablename__ = "memory_formation_effects"

    __table_args__ = (
        UniqueConstraint(
            "formation_job_id",
            name="uq_memory_formation_effects_job",
        ),
        ForeignKeyConstraint(
            ["formation_job_id", "organization_id"],
            [
                "memory_formation_jobs.id",
                "memory_formation_jobs.organization_id",
            ],
            name="fk_memory_formation_effects_job_organization",
            ondelete="CASCADE",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    formation_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    operations: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    applied_flags: Mapped[list[bool]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    completed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    outcomes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
