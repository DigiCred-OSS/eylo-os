"""Knowledgebase definitions and the grants that let agents use them.

The module owns *what exists and who may use it*; the socket owns how the
platform talks to a vendor. This file is the first half.

Three tables; the grant carries access policy and every chunk names its KB.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eylo.common.contracts.knowledgebase import KnowledgeAccess, KnowledgeScope
from eylo.common.models import EyloOrganizationModel
from eylo.common.sql_types import VectorType
from eylo.modules.knowledgebase.reindex import KnowledgeReindexState


class KnowledgebaseModel(EyloOrganizationModel):
    """One knowledgebase: a vendor, a scope, and the thing it belongs to."""

    __tablename__ = "knowledgebases"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledgebases_id_organization_id",
        ),
        Index(
            "uq_knowledgebases_conversation_scope_active",
            "organization_id",
            "scope_id",
            unique=True,
            postgresql_where=text("scope = 'conversation' AND deleted = false"),
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledgebases_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledgebases_target_embedding_config_organization",
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
            name="fk_knowledgebases_target_embedding_config_revision",
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
            name="fk_knowledgebases_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(vendor = 'pgvector' AND embedding_provider_config_id IS NOT NULL "
            "AND embedding_provider_config_revision IS NOT NULL "
            "AND embedding_provider IS NOT NULL AND embedding_endpoint IS NOT NULL "
            "AND embedding_model IS NOT NULL AND embedding_dimensions IS NOT NULL "
            "AND embedding_semantic_options IS NOT NULL "
            "AND embedding_space_id IS NOT NULL) OR "
            "(vendor <> 'pgvector' AND embedding_provider_config_id IS NULL "
            "AND embedding_provider_config_revision IS NULL "
            "AND embedding_provider IS NULL AND embedding_endpoint IS NULL "
            "AND embedding_model IS NULL AND embedding_dimensions IS NULL "
            "AND embedding_semantic_options IS NULL "
            "AND embedding_space_id IS NULL)",
            name="ck_knowledgebases_embedding_space",
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
            "(vendor = 'pgvector' AND reindex_state <> 'active' "
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
            name="ck_knowledgebases_reindex_state",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)

    # No default. An organization configures a vendor or has no knowledgebase —
    # picking one would decide what "similar" means on their behalf.
    vendor: Mapped[str] = mapped_column(String(64), nullable=False)

    scope: Mapped[KnowledgeScope] = mapped_column(
        # `values_callable` so Postgres stores the enum's *values*, not its
        # member names. Without it SQLAlchemy stores "ORGANIZATION" here while
        # `knowledge_chunks.scope` — a plain string column the vendors write
        # from `scope.value` — holds "organization", and the same concept has
        # two spellings one join apart.
        ENUM(
            KnowledgeScope,
            name="knowledge_scope_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        doc="Which of organization, agent or conversation this KB belongs to.",
    )
    # The organization, agent or conversation id, depending on `scope`. Not a
    # foreign key: it points at three different tables, and a nullable column
    # per scope would let a row claim two owners.
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Whether this KB accepts writes at all. A grant cannot exceed it, so an
    # append-only source stays read-only however it is granted.
    writable: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    embedding_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    embedding_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_semantic_options: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    embedding_space_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    reindex_state: Mapped[KnowledgeReindexState] = mapped_column(
        ENUM(
            KnowledgeReindexState,
            name="knowledge_reindex_state_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=KnowledgeReindexState.ACTIVE,
        server_default=KnowledgeReindexState.ACTIVE.value,
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


class KnowledgebaseGrantModel(EyloOrganizationModel):
    """An agent's access to a knowledgebase.

    The organization is carried explicitly and both references are composite.
    Service checks explain a bad request; the constraints make a cross-org
    grant impossible even when a new call path forgets those checks.

    **Access is a property of this row, not of the agent.** An agent has no
    inherent right to write; a grant does or does not carry it. That is what
    makes read-only the default rather than a convention someone remembers.
    """

    __tablename__ = "knowledgebase_grants"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_knowledgebase_grants_agent_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledgebase_grants_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint("agent_id", "knowledgebase_id"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    knowledgebase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    access: Mapped[KnowledgeAccess] = mapped_column(
        ENUM(
            KnowledgeAccess,
            name="knowledge_access_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=KnowledgeAccess.READ,
        server_default=KnowledgeAccess.READ.value,
        doc=(
            "READ by default. Without RBAC, an agent that can write to an "
            "organization-wide KB changes what every other conversation reads, "
            "so granting write has to be a decision someone made."
        ),
    )

    # Eager because every caller that loads a grant immediately needs the KB
    # behind it: the access checks read
    # `knowledgebase.writable` and `knowledgebase.scope`, so a lazy load would
    # be a guaranteed second query in an async session that cannot emit one.
    knowledgebase: Mapped[KnowledgebaseModel] = relationship(lazy="selectin")


class KnowledgeChunkModel(EyloOrganizationModel):
    """Stored chunks. Written by the vendors, never read by this module.

    Declared here so Alembic can see it and so one table serves both Postgres
    vendors — `embedding` is null for full-text search, and its query filters
    on that rather than on a separate table.
    """

    __tablename__ = "knowledge_chunks"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_chunks_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        Index(
            "uq_knowledge_chunks_fts_document_position",
            "knowledgebase_id",
            "document_id",
            "position",
            unique=True,
            postgresql_where=text("embedding_space_id IS NULL"),
        ),
        Index(
            "uq_knowledge_chunks_vector_document_position",
            "knowledgebase_id",
            "document_id",
            "position",
            "embedding_space_id",
            unique=True,
            postgresql_where=text("embedding_space_id IS NOT NULL"),
        ),
        Index(
            "ix_knowledge_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    knowledgebase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[str | None] = mapped_column(VectorType(), nullable=True)
    embedding_space_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    reindex_source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
