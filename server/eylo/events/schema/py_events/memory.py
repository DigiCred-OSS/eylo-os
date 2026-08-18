"""Content-free local event contracts for Memory product boundaries."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eylo.common.contracts.memory import MemoryLevel, MemoryOrigin
from eylo.common.contracts.reranking import RankingState
from eylo.events.schema.py_events.base import BaseEvent

SafeCode = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.-]+$"),
]
BoundedCount = Annotated[int, Field(ge=0, le=2_147_483_647)]
BoundedRevision = Annotated[int, Field(gt=0, le=2_147_483_647)]


class MemoryFactAction(StrEnum):
    ADDED = "added"
    UPDATED = "updated"
    EXPIRED = "expired"
    DELETED = "deleted"


class MemoryWorkTransition(StrEnum):
    QUEUED = "queued"
    ATTEMPT_STARTED = "attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryWorkState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryReconciliationTransition(StrEnum):
    QUEUED = "queued"
    ATTEMPT_STARTED = "attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STALE_ABANDONED = "stale_abandoned"


class MemoryReindexTransition(StrEnum):
    REINDEX_REQUIRED = "reindex_required"
    QUEUED = "queued"
    ATTEMPT_STARTED = "attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TARGET_DISCARDED = "target_discarded"


class MemoryIndexState(StrEnum):
    ACTIVE = "active"
    REQUIRED = "reindex_required"
    REINDEXING = "reindexing"
    FAILED = "failed"


class MemoryObservationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class MemoryFactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: UUID
    action: MemoryFactAction


class MemoryOutcomeSummary(BaseModel):
    """Bounded event projection of one completely accepted operation plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    considered: BoundedCount
    added: BoundedCount
    updated: BoundedCount
    deleted: BoundedCount
    noop: BoundedCount
    failed: BoundedCount

    @model_validator(mode="after")
    def complete_partition(self) -> MemoryOutcomeSummary:
        terminal = self.added + self.updated + self.deleted + self.noop + self.failed
        if terminal != self.considered:
            raise ValueError("Memory event outcomes must partition considered facts.")
        return self


class _MemoryEvent(BaseEvent):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID


class MemoryFactsChangedEvent(_MemoryEvent):
    memory_provider_config_id: UUID
    memory_provider_config_revision: BoundedRevision
    level: MemoryLevel
    owner_id: UUID
    source: MemoryOrigin
    changes: tuple[MemoryFactReference, ...] = Field(min_length=1, max_length=20)
    formation_job_id: UUID | None = None
    reconciliation_job_id: UUID | None = None


class MemoryFormationLifecycleEvent(_MemoryEvent):
    job_id: UUID
    conversation_id: UUID
    memory_provider_config_id: UUID
    memory_provider_config_revision: BoundedRevision
    transition: MemoryWorkTransition
    state: MemoryWorkState
    attempts: BoundedCount
    outcomes: MemoryOutcomeSummary | None = None
    failure_code: SafeCode | None = None


class MemoryReconciliationLifecycleEvent(_MemoryEvent):
    job_id: UUID
    memory_provider_config_id: UUID
    memory_provider_config_revision: BoundedRevision
    level: MemoryLevel
    owner_id: UUID
    generation: int = Field(gt=0, le=2_147_483_647)
    transition: MemoryReconciliationTransition
    state: MemoryWorkState
    attempts: BoundedCount
    considered_count: BoundedCount = 0
    duplicate_count: BoundedCount = 0
    superseded_count: BoundedCount = 0
    conflict_count: BoundedCount = 0
    unrelated_count: BoundedCount = 0
    failed_count: BoundedCount = 0
    failure_code: SafeCode | None = None


class MemoryReindexLifecycleEvent(_MemoryEvent):
    memory_provider_config_id: UUID
    job_id: UUID | None = None
    transition: MemoryReindexTransition
    state: MemoryWorkState | None = None
    index_state: MemoryIndexState
    source_embedding_space_id: str = Field(min_length=1, max_length=64)
    target_embedding_space_id: str = Field(min_length=1, max_length=64)
    processed_count: BoundedCount = 0
    total_count: BoundedCount = 0
    failure_code: SafeCode | None = None


class MemoryRecallObservedEvent(_MemoryEvent):
    agent_id: UUID
    conversation_id: UUID
    outcome: MemoryObservationOutcome
    requested_limit: int = Field(ge=1, le=100)
    candidate_count: BoundedCount
    returned_count: BoundedCount
    conflict_count: BoundedCount
    ranking_state: RankingState
    ranking_reason: SafeCode | None = None
    duration_ms: int = Field(ge=0, le=86_400_000)
    failure_code: SafeCode | None = None


MemoryPostCommitEvent = (
    MemoryFactsChangedEvent
    | MemoryFormationLifecycleEvent
    | MemoryReconciliationLifecycleEvent
    | MemoryReindexLifecycleEvent
)
