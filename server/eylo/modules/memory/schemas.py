"""Private operator projections for the Memory product surface."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from eylo.absurd_work import DurableState
from eylo.common.contracts.memory import (
    MemoryEvent,
    MemoryLevel,
    MemoryProvenance,
)
from eylo.common.contracts.memory_reconciliation import (
    MemoryIntegrityState,
    MemoryRelationshipKind,
)
from eylo.modules.memory.reindex import MemoryReindexState


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class MemorySort(StrEnum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    LAST_RECALLED_AT = "last_recalled_at"
    EXPIRES_AT = "expires_at"
    RECALL_COUNT = "recall_count"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class MemoryRelationshipRole(StrEnum):
    SOURCE = "source"
    TARGET = "target"


class MemoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    content: str
    level: MemoryLevel
    subject_id: UUID
    subject_label: str
    status: MemoryStatus
    integrity: MemoryIntegrityState
    source_conversation_id: UUID
    recall_count: int = Field(ge=0)
    last_recalled_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MemoryChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    event: MemoryEvent
    before: str | None
    after: str | None
    created_at: datetime
    source_conversation_id: UUID | None
    provenance: MemoryProvenance


class MemoryRelationshipRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: MemoryRelationshipKind
    memory_role: MemoryRelationshipRole
    current: bool
    related_memory: MemoryRead
    reconciliation_job_id: UUID
    created_at: datetime


class MemoryReconciliationJobRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    state: DurableState
    generation: int = Field(gt=0)
    change_count: int = Field(ge=1, le=20)
    considered_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    superseded_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    unrelated_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    attempts: int = Field(ge=0)
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    created_at: datetime


class MemoryDetailRead(MemoryRead):
    metadata: dict
    provenance: MemoryProvenance
    history: list[MemoryChangeRead]
    relationships: list[MemoryRelationshipRead]
    latest_reconciliation: MemoryReconciliationJobRead | None


class MemoryListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MemoryRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class MemoryEmbeddingSpaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_config_id: UUID
    provider_config_revision: int = Field(gt=0)
    provider: str
    model: str
    dimensions: int = Field(gt=0)
    space_id: str


class MemoryReindexJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    memory_provider_config_id: UUID
    state: DurableState
    source_embedding_space_id: str
    target_embedding_provider_config_id: UUID
    target_embedding_provider_config_revision: int = Field(gt=0)
    target_embedding_provider: str
    target_embedding_model: str
    target_embedding_dimensions: int = Field(gt=0)
    target_embedding_semantic_options: dict
    target_embedding_space_id: str
    source_fact_count: int = Field(ge=0)
    indexed_fact_count: int = Field(ge=0)
    attempts: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class MemoryReindexStatusRead(BaseModel):
    """Current, staged, and available vector authority for one Memory config."""

    model_config = ConfigDict(extra="forbid")

    initialized: bool
    state: MemoryReindexState | None
    active_space: MemoryEmbeddingSpaceRead | None
    target_space: MemoryEmbeddingSpaceRead | None
    available_space: MemoryEmbeddingSpaceRead | None
    update_available: bool
    last_error: str | None
    latest_job: MemoryReindexJobRead | None


__all__ = [
    "MemoryChangeRead",
    "MemoryDetailRead",
    "MemoryListRead",
    "MemoryRead",
    "MemoryEmbeddingSpaceRead",
    "MemoryReconciliationJobRead",
    "MemoryReindexJobRead",
    "MemoryReindexStatusRead",
    "MemoryRelationshipRead",
    "MemoryRelationshipRole",
    "MemorySort",
    "MemoryStatus",
    "SortDirection",
]
