"""Canonical product rows for Absurd-owned knowledge work.

The row is filed and committed before an Absurd task is spawned. It owns the
operator-visible lifecycle, pinned provider authority, result and audit attempt
count. The exact `absurd_task_id` binds it to execution. Absurd, not this module,
owns claims, leases, retries and heartbeats.

A lost producer callback leaves an unbound PostgreSQL row. The periodic nudge
only repeats the idempotent spawn; it never claims or executes knowledge work.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
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

from eylo.absurd_work import TERMINAL_STATES as DURABLE_TERMINAL_STATES
from eylo.absurd_work import (
    AbsurdBoundWorkMixin,
    DurableState,
)
from eylo.common.contracts.storage import StorageAuthority, StorageLocator
from eylo.common.models import EyloOrganizationModel

# Content is stored on the job row rather than in object storage. That is a
# deliberate ceiling, not an oversight: inline content means one write to
# enqueue and no second system to be inconsistent with, and 1 MB of text is far
# more than the documents this path was built for. Larger corpora need a
# storage-backed source, which is a different feature and should say so rather
# than silently truncating here.
MAX_CONTENT_BYTES = 1_000_000


# The state machine now lives in `eylo/common/durable`, extracted once a third
# caller needed it. These aliases keep the module's own vocabulary — an
# ingestion job is in a state, not in a "durable state" — without a second
# enum that could drift from the first.
IngestionState = DurableState
TERMINAL_STATES = DURABLE_TERMINAL_STATES


class KnowledgeIngestionJobModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One document's journey into one knowledgebase.

    Absurd owns execution and retries. This row owns what makes the work a
    document ingestion plus its canonical product lifecycle and result.
    """

    __tablename__ = "knowledge_ingestion_jobs"
    __durable_enum_name__ = "knowledge_ingestion_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledge_ingestion_jobs_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_knowledge_jobs_user_session_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_jobs_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["corpus_import_id", "organization_id"],
            ["knowledge_corpus_imports.id", "knowledge_corpus_imports.organization_id"],
            name="fk_knowledge_jobs_corpus_import_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_jobs_storage_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledge_jobs_storage_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_jobs_embedding_config_organization",
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
            name="fk_knowledge_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(content IS NOT NULL AND storage_key IS NULL AND "
            "storage_provider_config_id IS NULL AND "
            "storage_provider_config_revision IS NULL AND storage_provider IS NULL "
            "AND storage_authority IS NULL) OR "
            "(content IS NULL AND storage_key IS NOT NULL AND "
            "storage_provider_config_id IS NOT NULL AND "
            "storage_provider_config_revision IS NOT NULL AND storage_provider IS NOT NULL "
            "AND storage_authority IS NOT NULL)",
            name="ck_knowledge_ingestion_jobs_one_source",
        ),
        CheckConstraint(
            "(embedding_provider_config_id IS NULL "
            "AND embedding_provider_config_revision IS NULL "
            "AND embedding_provider IS NULL AND embedding_endpoint IS NULL "
            "AND embedding_model IS NULL AND embedding_dimensions IS NULL "
            "AND embedding_semantic_options IS NULL "
            "AND embedding_space_id IS NULL) OR "
            "(embedding_provider_config_id IS NOT NULL "
            "AND embedding_provider_config_revision IS NOT NULL "
            "AND embedding_provider IS NOT NULL AND embedding_endpoint IS NOT NULL "
            "AND embedding_model IS NOT NULL AND embedding_dimensions IS NOT NULL "
            "AND embedding_semantic_options IS NOT NULL "
            "AND embedding_space_id IS NOT NULL)",
            name="ck_knowledge_jobs_embedding_space",
        ),
        Index(
            "uq_knowledge_ingestion_jobs_active_document",
            "knowledgebase_id",
            "document_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
    )

    knowledgebase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # The document's derived identity, copied here at enqueue time. Stored
    # rather than recomputed so an operator can see which document a job is
    # for without loading its content, and so two jobs for the same document
    # are recognisable as such.
    document_key: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Exactly one of these is set, and the difference is where the bytes live.
    #
    # `content` is a document handed straight to the platform — an agent's
    # write, an operator pasting a policy. `storage_key` is a document that
    # lives in the organization's own storage and is fetched at run time.
    #
    # Fetching late is the point of the second form: a corpus import files
    # thousands of jobs in one pass without reading a byte, and each document
    # is pulled only when a worker is ready to index it. It also means the
    # worker indexes what the object says *now* rather than what it said when
    # the import was queued — correct for a source, and safe because the
    # derived identity replaces rather than duplicates.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    storage_provider_config_revision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    storage_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_authority: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
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

    # Which import filed this job, when one did. Null for a job somebody
    # submitted directly, which is why this is nullable rather than a required
    # parent: an inline document is not part of a corpus.
    corpus_import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # There is no chunk_count column. Only the Postgres vendors chunk in a way
    # this module could count, and a column that is meaningful for two vendors
    # and null for the rest is a surface that lies about what it knows. The
    # protocol reports a document id; that is what gets stored.


# What a corpus import will read. Higher than the inline ceiling because the
# bytes are already stored — nothing is being pushed through a request — but
# still bounded: the worker holds the whole object in memory to decode it, and
# an unbounded read is how one oversized file takes down a worker that then
# never reports why.
MAX_STORAGE_OBJECT_BYTES = 20_000_000

# How many objects one import will enumerate. A ceiling that is stated and
# logged when hit, rather than a silent truncation that would leave an operator
# believing their corpus was imported whole.
MAX_CORPUS_OBJECTS = 5_000


# Same machine, same aliases. The one difference from the upstream shape is
# vocabulary: a sweep that finished is "succeeded" like everything else, and
# `COMPLETED` is kept only as a name for it so existing code reads naturally.
CorpusImportState = DurableState
CORPUS_TERMINAL_STATES = DURABLE_TERMINAL_STATES


class KnowledgeCorpusImportModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One sweep of a storage prefix into a knowledgebase."""

    __tablename__ = "knowledge_corpus_imports"
    __durable_enum_name__ = "knowledge_corpus_import_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledge_corpus_imports_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_corpus_imports_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_corpus_imports_storage_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_corpus_imports_storage_config_revision",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_knowledge_corpus_imports_active_source",
            "knowledgebase_id",
            "import_key",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
    )

    knowledgebase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # The storage prefix to sweep. Empty means the whole root, which is a
    # legitimate thing to want and so is allowed rather than guarded against.
    prefix: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    import_key: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    storage_provider_config_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    storage_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_authority: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # What the sweep found and what it filed. Two numbers rather than one,
    # because they differ whenever an object was skipped — unreadable, too
    # large, or already queued — and an operator seeing "discovered 900, queued
    # 812" knows to look, where a single count would hide it.
    discovered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    queued_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    skipped: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, doc="Objects that were not queued, and why."
    )


class KnowledgeReindexJobModel(EyloOrganizationModel, AbsurdBoundWorkMixin):
    """One immutable source-space to target-space knowledgebase transition."""

    __tablename__ = "knowledge_reindex_jobs"
    __durable_enum_name__ = "knowledge_reindex_job_state_enum"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledge_reindex_jobs_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_reindex_jobs_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_reindex_jobs_source_config_organization",
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
            name="fk_knowledge_reindex_jobs_source_config_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_reindex_jobs_target_config_organization",
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
            name="fk_knowledge_reindex_jobs_target_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_embedding_space_id <> target_embedding_space_id",
            name="ck_knowledge_reindex_jobs_distinct_spaces",
        ),
        Index(
            "uq_knowledge_reindex_jobs_active_knowledgebase",
            "knowledgebase_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running') AND deleted IS FALSE"
            ),
        ),
    )

    knowledgebase_id: Mapped[uuid.UUID] = mapped_column(
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
    source_embedding_model: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
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
    target_embedding_model: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    target_embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    target_embedding_semantic_options: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )
    target_embedding_space_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    source_chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    indexed_chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


def storage_authority_from_record(
    record: KnowledgeCorpusImportModel | KnowledgeIngestionJobModel,
) -> StorageAuthority:
    """Rebuild the immutable authority captured on a corpus or job row."""
    return StorageAuthority(
        organization_id=record.organization_id,
        provider_config_id=record.storage_provider_config_id,
        provider_config_revision=record.storage_provider_config_revision,
        provider=record.storage_provider,
        location=record.storage_authority,
    )


def storage_locator_from_job(job: KnowledgeIngestionJobModel) -> StorageLocator:
    if job.storage_key is None:
        raise ValueError(f"Knowledge ingestion job {job.id} has no storage key.")
    return storage_authority_from_record(job).locate(job.storage_key)
