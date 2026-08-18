"""Request and response shapes for the knowledgebase module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.knowledgebase import (
    MAX_KNOWLEDGE_SOURCE_URI_CHARS,
    KnowledgeAccess,
    KnowledgeScope,
)
from eylo.modules.knowledgebase.extraction import SUPPORTED_EXTENSIONS
from eylo.modules.knowledgebase.jobs import (
    MAX_CONTENT_BYTES,
    CorpusImportState,
    IngestionState,
)
from eylo.modules.knowledgebase.reindex import KnowledgeReindexState
from eylo.modules.knowledgebase.vendors import KnowledgebaseMetadata


class KnowledgebaseCreate(BaseModel):
    """Creating a knowledgebase.

    `vendor` has no default. Choosing one on the operator's behalf would decide
    what "similar" means for every future query — a Postgres FTS KB and a
    pgvector KB answer the same question differently, and neither is the
    obvious right answer.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    vendor: str = Field(min_length=1, max_length=64)
    scope: KnowledgeScope
    scope_id: str = Field(min_length=1, max_length=64)
    writable: bool = Field(
        default=False,
        description=(
            "Whether this knowledgebase accepts writes at all. A grant cannot "
            "exceed it, so an imported source stays read-only however it is "
            "granted."
        ),
    )
    embedding_provider_config_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Required for pgvector and rejected for vendors that do not embed. "
            "The selected ready revision becomes this knowledgebase's immutable "
            "vector space."
        ),
    )
    metadata: KnowledgebaseMetadata | None = None


class KnowledgebaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    writable: bool | None = None
    metadata: KnowledgebaseMetadata | None = None


class KnowledgebaseReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding_provider_config_id: uuid.UUID


class KnowledgebaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    name: str
    slug: str
    vendor: str
    scope: KnowledgeScope
    scope_id: str
    writable: bool
    embedding_provider_config_id: uuid.UUID | None
    embedding_provider_config_revision: int | None
    embedding_provider: str | None
    embedding_endpoint: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    embedding_semantic_options: dict | None
    embedding_space_id: str | None
    reindex_state: KnowledgeReindexState
    target_embedding_provider_config_id: uuid.UUID | None
    target_embedding_provider_config_revision: int | None
    target_embedding_provider: str | None
    target_embedding_endpoint: str | None
    target_embedding_model: str | None
    target_embedding_dimensions: int | None
    target_embedding_semantic_options: dict | None
    target_embedding_space_id: str | None
    reindex_last_error: str | None
    metadata: KnowledgebaseMetadata | None = Field(validation_alias="meta")
    created_at: datetime
    updated_at: datetime


class GrantCreate(BaseModel):
    """Granting an agent access to a knowledgebase.

    `access` defaults to READ. An unspecified grant is a read grant — the
    caller has to say `READ_WRITE` to get it, so write access is always
    something someone chose.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID
    knowledgebase_id: uuid.UUID
    access: KnowledgeAccess = KnowledgeAccess.READ


class GrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    agent_id: uuid.UUID
    knowledgebase_id: uuid.UUID
    access: KnowledgeAccess


class WidgetKnowledgeUploadCapabilityRead(BaseModel):
    """Whether the pinned Agent revision accepts conversation file uploads."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool


class WidgetKnowledgeIngestionRead(BaseModel):
    """Narrow public receipt for one conversation file ingestion."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    document_id: uuid.UUID
    state: IngestionState
    title: str | None
    source_uri: str | None
    last_error: str | None


class IngestRequest(BaseModel):
    """Submitting a document for ingestion.

    `scope` and `scope_id` are not here. A document belongs to the
    knowledgebase it is ingested into, and that knowledgebase already has a
    scope — accepting one here would let a caller file an agent-scoped document
    into an organization-wide knowledgebase, where every agent would then read
    it.
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=MAX_CONTENT_BYTES)
    title: str | None = Field(default=None, max_length=512)
    source_uri: str | None = Field(
        default=None,
        max_length=MAX_KNOWLEDGE_SOURCE_URI_CHARS,
        description=(
            "A durable address for this document. When set, it becomes the "
            "document's identity, so re-ingesting the same URI replaces the "
            "previous version instead of adding a second copy. Without it, "
            "identity falls back to the content itself and an edited document "
            "becomes a new one."
        ),
    )
    metadata: dict | None = None


class CorpusImportRequest(BaseModel):
    """Sweeping a storage prefix into this knowledgebase.

    No vendor field: the storage vendor is whatever the organization
    configured, the same one recordings use. A knowledgebase that could name
    its own storage would be a second place to configure credentials, and a
    second place for them to be wrong.
    """

    model_config = ConfigDict(extra="forbid")

    storage_provider_config_id: uuid.UUID = Field(
        description=(
            "Explicit ready storage config whose current revision is pinned to "
            "the import and every child job."
        )
    )

    prefix: str = Field(
        default="",
        max_length=1024,
        description=(
            "Storage prefix to sweep, e.g. 'policies/'. Empty sweeps the whole "
            "root. Objects are matched by prefix, not by glob. Readable file "
            "types: " + ", ".join(SUPPORTED_EXTENSIONS) + ". Anything else is "
            "skipped and reported on the import. Legacy .doc and .xls are "
            "different: .xls is read, .doc is not — it fails with a message "
            "asking for .docx, rather than being silently passed over."
        ),
    )


class CorpusImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    knowledgebase_id: uuid.UUID
    state: CorpusImportState
    prefix: str
    storage_provider_config_id: uuid.UUID
    storage_provider_config_revision: int
    storage_provider: str
    discovered_count: int
    queued_count: int
    skipped: dict | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    knowledgebase_id: uuid.UUID
    state: IngestionState
    document_id: uuid.UUID
    document_key: str
    title: str | None
    source_uri: str | None
    storage_key: str | None
    storage_provider_config_id: uuid.UUID | None
    storage_provider_config_revision: int | None
    storage_provider: str | None
    embedding_provider_config_id: uuid.UUID | None
    embedding_provider_config_revision: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    embedding_semantic_options: dict | None
    embedding_space_id: str | None
    corpus_import_id: uuid.UUID | None
    attempts: int
    max_attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeReindexJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    knowledgebase_id: uuid.UUID
    state: IngestionState
    source_embedding_space_id: str
    target_embedding_provider_config_id: uuid.UUID
    target_embedding_provider_config_revision: int
    target_embedding_provider: str
    target_embedding_model: str
    target_embedding_dimensions: int
    target_embedding_semantic_options: dict
    target_embedding_space_id: str
    source_chunk_count: int
    indexed_chunk_count: int
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeEmbeddingSpaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_config_id: uuid.UUID
    provider_config_revision: int = Field(gt=0)
    provider: str
    model: str
    dimensions: int = Field(gt=0)
    space_id: str


class KnowledgeReindexStatusRead(BaseModel):
    """Current, staged, and available vector authority for one knowledgebase."""

    model_config = ConfigDict(extra="forbid")

    state: KnowledgeReindexState
    active_space: KnowledgeEmbeddingSpaceRead
    target_space: KnowledgeEmbeddingSpaceRead | None
    available_space: KnowledgeEmbeddingSpaceRead | None
    update_available: bool
    last_error: str | None
    latest_job: KnowledgeReindexJobRead | None
