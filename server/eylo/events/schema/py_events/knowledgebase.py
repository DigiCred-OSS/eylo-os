"""Content-free local event contracts for Knowledgebase product boundaries."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from eylo.common.contracts.knowledgebase import KnowledgeAccess
from eylo.common.contracts.reranking import RankingState
from eylo.events.schema.py_events.base import BaseEvent

SafeCode = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.-]+$"),
]
BoundedCount = Annotated[int, Field(ge=0, le=2_147_483_647)]


class KnowledgebaseTransition(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class KnowledgebaseChangedField(StrEnum):
    NAME = "name"
    WRITABLE = "writable"
    METADATA = "metadata"


class KnowledgebaseAccessTransition(StrEnum):
    GRANTED = "granted"
    CHANGED = "changed"
    REVOKED = "revoked"


class KnowledgeWorkTransition(StrEnum):
    QUEUED = "queued"
    ATTEMPT_STARTED = "attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class KnowledgeWorkState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class KnowledgeReindexTransition(StrEnum):
    QUEUED = "queued"
    ATTEMPT_STARTED = "attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TARGET_DISCARDED = "target_discarded"


class KnowledgeIndexState(StrEnum):
    ACTIVE = "active"
    REQUIRED = "reindex_required"
    REINDEXING = "reindexing"
    FAILED = "failed"


class KnowledgeObservationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class _KnowledgeEvent(BaseEvent):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID


class KnowledgebaseLifecycleEvent(_KnowledgeEvent):
    knowledgebase_id: UUID
    transition: KnowledgebaseTransition
    changed_fields: tuple[KnowledgebaseChangedField, ...] = Field(
        default_factory=tuple,
        max_length=len(KnowledgebaseChangedField),
    )
    affected_ingestion_jobs: BoundedCount = 0
    affected_corpus_imports: BoundedCount = 0
    affected_reindex_jobs: BoundedCount = 0
    deleted_chunks: BoundedCount = 0
    revoked_grants: BoundedCount = 0


class KnowledgebaseAccessChangedEvent(_KnowledgeEvent):
    knowledgebase_id: UUID
    agent_id: UUID
    transition: KnowledgebaseAccessTransition
    access: KnowledgeAccess | None = None


class KnowledgeIngestionLifecycleEvent(_KnowledgeEvent):
    knowledgebase_id: UUID
    job_id: UUID
    document_id: UUID
    corpus_import_id: UUID | None = None
    transition: KnowledgeWorkTransition
    state: KnowledgeWorkState
    attempts: BoundedCount
    failure_code: SafeCode | None = None


class KnowledgeCorpusImportLifecycleEvent(_KnowledgeEvent):
    knowledgebase_id: UUID
    import_id: UUID
    transition: KnowledgeWorkTransition
    state: KnowledgeWorkState
    attempts: BoundedCount
    discovered_count: BoundedCount = 0
    queued_count: BoundedCount = 0
    skipped_count: BoundedCount = 0
    failure_code: SafeCode | None = None


class KnowledgeReindexLifecycleEvent(_KnowledgeEvent):
    knowledgebase_id: UUID
    job_id: UUID
    transition: KnowledgeReindexTransition
    state: KnowledgeWorkState
    index_state: KnowledgeIndexState
    source_embedding_space_id: str = Field(min_length=1, max_length=64)
    target_embedding_space_id: str = Field(min_length=1, max_length=64)
    processed_count: BoundedCount = 0
    total_count: BoundedCount = 0
    failure_code: SafeCode | None = None


class KnowledgeQueryObservedEvent(_KnowledgeEvent):
    agent_id: UUID
    conversation_id: UUID | None = None
    outcome: KnowledgeObservationOutcome
    requested_knowledgebase_count: BoundedCount
    available_knowledgebase_count: BoundedCount
    failed_knowledgebase_count: BoundedCount
    candidate_count: BoundedCount
    returned_count: BoundedCount
    ranking_state: RankingState
    ranking_reason: SafeCode | None = None
    duration_ms: int = Field(ge=0, le=86_400_000)
    failure_code: SafeCode | None = None


KnowledgePostCommitEvent = (
    KnowledgebaseLifecycleEvent
    | KnowledgebaseAccessChangedEvent
    | KnowledgeIngestionLifecycleEvent
    | KnowledgeCorpusImportLifecycleEvent
    | KnowledgeReindexLifecycleEvent
)
