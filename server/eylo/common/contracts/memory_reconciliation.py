"""Vendor-neutral Memory reconciliation decisions and limits."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eylo.common.contracts.memory import (
    MEMORY_MAX_FACT_BYTES,
    MEMORY_MAX_FACT_CHARS,
)

MEMORY_RECONCILIATION_MAX_CHANGES = 20
MEMORY_RECONCILIATION_MAX_CANDIDATES = 8
MEMORY_RECONCILIATION_MAX_RESPONSE_BYTES = 32_000


class MemoryRelationshipKind(StrEnum):
    DUPLICATE_OF = "duplicate_of"
    SUPERSEDED_BY = "superseded_by"
    CONFLICTS_WITH = "conflicts_with"


class MemoryIntegrityState(StrEnum):
    CHECKING = "checking"
    CONFLICTED = "conflicted"
    CONSOLIDATED = "consolidated"
    HEALTHY = "healthy"


class MemoryReconciliationOutcome(StrEnum):
    DUPLICATE = "duplicate"
    SUPERSEDES = "supersedes"
    CONFLICTS = "conflicts"
    UNRELATED = "unrelated"


class MemoryReconciliationSettlementReason(StrEnum):
    EXPIRED = "expired"
    DELETED = "deleted"


class MemoryReconciliationCandidate(BaseModel):
    """One same-partition candidate presented as untrusted evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: UUID
    state_revision: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=MEMORY_MAX_FACT_CHARS)

    @model_validator(mode="after")
    def bounded_content(self) -> "MemoryReconciliationCandidate":
        if len(self.content.encode("utf-8")) > MEMORY_MAX_FACT_BYTES:
            raise ValueError("Memory reconciliation candidate exceeds its byte limit.")
        return self


class MemoryReconciliationInput(BaseModel):
    """One changed current fact and its bounded same-partition candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: UUID
    state_revision: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=MEMORY_MAX_FACT_CHARS)
    evidence_change_ids: tuple[UUID, ...] = Field(min_length=1)
    candidates: tuple[MemoryReconciliationCandidate, ...] = Field(
        max_length=MEMORY_RECONCILIATION_MAX_CANDIDATES
    )

    @model_validator(mode="after")
    def bounded_unique_candidates(self) -> "MemoryReconciliationInput":
        if len(self.content.encode("utf-8")) > MEMORY_MAX_FACT_BYTES:
            raise ValueError("Memory reconciliation input exceeds its byte limit.")
        ids = [candidate.memory_id for candidate in self.candidates]
        if self.memory_id in ids or len(ids) != len(set(ids)):
            raise ValueError("Memory reconciliation candidates must be unique peers.")
        return self


class MemoryReconciliationSettlement(BaseModel):
    """One exact inactive fact that needs no semantic comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: UUID
    state_revision: int = Field(gt=0)
    evidence_change_ids: tuple[UUID, ...] = Field(min_length=1)
    reason: MemoryReconciliationSettlementReason


class MemoryReconciliationBatch(BaseModel):
    """Immutable semantic inputs plus deterministic lifecycle settlements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inputs: tuple[MemoryReconciliationInput, ...] = Field(
        max_length=MEMORY_RECONCILIATION_MAX_CHANGES
    )
    settlements: tuple[MemoryReconciliationSettlement, ...] = Field(
        max_length=MEMORY_RECONCILIATION_MAX_CHANGES
    )

    @model_validator(mode="after")
    def bounded_unique_facts(self) -> "MemoryReconciliationBatch":
        ids = [item.memory_id for item in (*self.inputs, *self.settlements)]
        if len(ids) > MEMORY_RECONCILIATION_MAX_CHANGES:
            raise ValueError("Memory reconciliation batch exceeds its fact limit.")
        if len(ids) != len(set(ids)):
            raise ValueError("Memory reconciliation batch repeats a fact.")
        return self


class MemoryReconciliationDecision(BaseModel):
    """One lifecycle-neutral or relationship decision; no reasoning text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: UUID
    observed_state_revision: int = Field(gt=0)
    outcome: MemoryReconciliationOutcome
    related_memory_id: UUID | None = None
    related_state_revision: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exact_relation(self) -> "MemoryReconciliationDecision":
        has_related = (
            self.related_memory_id is not None
            or self.related_state_revision is not None
        )
        if self.outcome is MemoryReconciliationOutcome.UNRELATED:
            if has_related:
                raise ValueError("Unrelated Memory decisions cannot name a fact.")
        elif (
            self.related_memory_id is None
            or self.related_state_revision is None
            or self.related_memory_id == self.memory_id
        ):
            raise ValueError("Related Memory decisions require another exact fact.")
        return self


class MemoryReconciliationProposal(BaseModel):
    """The complete bounded decision set returned by the configured LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decisions: tuple[MemoryReconciliationDecision, ...] = Field(
        max_length=MEMORY_RECONCILIATION_MAX_CHANGES
    )


__all__ = [
    "MEMORY_RECONCILIATION_MAX_CANDIDATES",
    "MEMORY_RECONCILIATION_MAX_CHANGES",
    "MEMORY_RECONCILIATION_MAX_RESPONSE_BYTES",
    "MemoryIntegrityState",
    "MemoryReconciliationBatch",
    "MemoryReconciliationCandidate",
    "MemoryReconciliationDecision",
    "MemoryReconciliationInput",
    "MemoryReconciliationOutcome",
    "MemoryReconciliationProposal",
    "MemoryReconciliationSettlement",
    "MemoryReconciliationSettlementReason",
    "MemoryRelationshipKind",
]
