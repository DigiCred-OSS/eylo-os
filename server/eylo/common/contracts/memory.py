"""Vendor-neutral memory value contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eylo.common.contracts.reranking import RankingMetadata

MEMORY_MAX_FACT_CHARS = 500
MEMORY_MAX_FACT_BYTES = 2_000
MEMORY_MAX_QUERY_CHARS = 2_000
MEMORY_MAX_QUERY_BYTES = 8_000
MEMORY_MAX_MESSAGE_CHARS = 2_000
MEMORY_MAX_MESSAGE_BYTES = 8_000
MEMORY_MAX_EXCHANGE_BYTES = 40_000
MEMORY_MAX_WINDOW_MESSAGES = 20
MEMORY_MAX_OPERATIONS = 20
MEMORY_MAX_EXTRACTOR_RESPONSE_BYTES = 32_000
MEMORY_MAX_SEARCH_RESULTS = 100


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


class MemoryLevel(StrEnum):
    """The product subject that owns one remembered fact."""

    AGENT = "agent"
    USER = "user"
    CONVERSATION = "conversation"


class MemoryScope(BaseModel):
    """The exact tenant, level, and stable subject for one memory fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: uuid.UUID
    level: MemoryLevel
    owner_id: uuid.UUID

    @property
    def conversation_id(self) -> uuid.UUID | None:
        """Return the owner only when this is Conversation memory."""
        if self.level is MemoryLevel.CONVERSATION:
            return self.owner_id
        return None


class MemoryMessageRole(StrEnum):
    """Roles the extractor is allowed to learn from."""

    USER = "user"
    ASSISTANT = "assistant"


class MemorySourceReference(BaseModel):
    """Content-free provenance for one persisted conversation message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: uuid.UUID
    participant_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    agent_revision: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exact_agent_revision(self) -> "MemorySourceReference":
        if (self.agent_id is None) != (self.agent_revision is None):
            raise ValueError("Memory source agent authority must be exact.")
        return self


class MemoryInputMessage(BaseModel):
    """Bounded extractor input with exact persisted evidence references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: MemoryMessageRole
    content: str = Field(min_length=1, max_length=MEMORY_MAX_MESSAGE_CHARS)
    sources: tuple[MemorySourceReference, ...] = Field(
        min_length=1,
        max_length=MEMORY_MAX_WINDOW_MESSAGES,
    )

    @model_validator(mode="after")
    def bounded_content(self) -> "MemoryInputMessage":
        if _utf8_size(self.content) > MEMORY_MAX_MESSAGE_BYTES:
            raise ValueError("Memory input message exceeds its byte limit.")
        return self


class MemoryOrigin(StrEnum):
    """The product flow that asked for a fact transition."""

    AUTOMATIC_FORMATION = "automatic_formation"
    AUTOMATIC_RECONCILIATION = "automatic_reconciliation"
    AGENT_TOOL = "agent_tool"
    MEMBER_CORRECTION = "member_correction"


class MemoryActorKind(StrEnum):
    """Organization-authorized principals that can deliberately change memory."""

    AGENT_PARTICIPANT = "agent_participant"
    ORGANIZATION_MEMBER = "organization_member"


class MemoryActor(BaseModel):
    """The exact principal responsible for a deliberate memory action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: MemoryActorKind
    actor_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    agent_revision: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exact_actor_authority(self) -> "MemoryActor":
        has_agent = self.agent_id is not None or self.agent_revision is not None
        if self.kind is MemoryActorKind.AGENT_PARTICIPANT:
            if self.agent_id is None or self.agent_revision is None:
                raise ValueError("Agent memory actors require an exact revision.")
        elif has_agent:
            raise ValueError("Only agent participants can carry agent authority.")
        return self


class MemoryExtractionAuthority(BaseModel):
    """Exact configured model and prompt authority used to infer a transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_config_id: uuid.UUID
    provider_config_revision: int = Field(gt=0)
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=255)
    prompt_revision: str = Field(min_length=1, max_length=64)


class MemoryProvenance(BaseModel):
    """Typed origin evidence kept separately from lifecycle ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    origin: MemoryOrigin
    source_conversation_id: uuid.UUID | None = None
    source_messages: tuple[MemorySourceReference, ...]
    actor: MemoryActor | None
    formation_job_id: uuid.UUID | None
    reconciliation_job_id: uuid.UUID | None = None
    extraction: MemoryExtractionAuthority | None

    @model_validator(mode="after")
    def complete_origin(self) -> "MemoryProvenance":
        if self.origin is MemoryOrigin.AUTOMATIC_FORMATION:
            if (
                self.source_conversation_id is None
                or not self.source_messages
                or self.formation_job_id is None
                or self.reconciliation_job_id is not None
                or self.extraction is None
                or self.actor is not None
            ):
                raise ValueError("Automatic memory provenance is incomplete.")
        elif self.origin is MemoryOrigin.AUTOMATIC_RECONCILIATION:
            if (
                self.source_conversation_id is not None
                or self.source_messages
                or self.actor is not None
                or self.formation_job_id is not None
                or self.reconciliation_job_id is None
                or self.extraction is None
            ):
                raise ValueError("Automatic reconciliation provenance is incomplete.")
        elif self.origin is MemoryOrigin.AGENT_TOOL:
            if (
                self.source_conversation_id is None
                or not self.source_messages
                or self.formation_job_id is not None
                or self.reconciliation_job_id is not None
                or self.actor is None
                or self.actor.kind is not MemoryActorKind.AGENT_PARTICIPANT
            ):
                raise ValueError("Agent-tool memory provenance is incomplete.")
        elif (
            self.formation_job_id is not None
            or self.reconciliation_job_id is not None
            or self.extraction is not None
            or self.actor is None
            or self.actor.kind is not MemoryActorKind.ORGANIZATION_MEMBER
        ):
            raise ValueError("Member-correction memory provenance is incomplete.")
        return self


class MemoryEvent(StrEnum):
    """What happened to a memory. mem0's vocabulary, and the history's."""

    ADD = "add"
    UPDATE = "update"
    EXPIRE = "expire"
    DELETE = "delete"
    NOOP = "noop"


class Memory(BaseModel):
    """One remembered fact."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    content: str
    scope: MemoryScope
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: MemoryProvenance


class MemoryUpdateResult(BaseModel):
    """The current fact plus whether a correction changed durable state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory: Memory
    changed: bool


class MemoryResult(BaseModel):
    """A memory retrieved by search, with its relevance.

    `score` is not comparable across vendors — the same caveat the
    knowledgebase carries, for the same reason. Rank within one result set.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    content: str
    score: float
    scope: MemoryScope
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: MemoryProvenance


class MemoryConflictFact(BaseModel):
    """One current fact inside an unresolved, untrusted conflict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    content: str = Field(min_length=1, max_length=MEMORY_MAX_FACT_CHARS)
    scope: MemoryScope
    updated_at: datetime

    @model_validator(mode="after")
    def bounded_content(self) -> "MemoryConflictFact":
        if _utf8_size(self.content) > MEMORY_MAX_FACT_BYTES:
            raise ValueError("Memory conflict fact exceeds its byte limit.")
        return self


class MemoryConflictEvidence(BaseModel):
    """One current revision-fenced conflict relevant to a recalled fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: uuid.UUID
    facts: tuple[MemoryConflictFact, MemoryConflictFact]
    detected_at: datetime

    @model_validator(mode="after")
    def exact_pair(self) -> "MemoryConflictEvidence":
        left, right = self.facts
        if left.id == right.id or left.scope != right.scope:
            raise ValueError("Memory conflict evidence requires two scoped facts.")
        return self


class MemoryRecall(BaseModel):
    """Ordered recall, unresolved evidence, and optional-ranking outcome."""

    model_config = ConfigDict(extra="forbid")

    memories: list[MemoryResult]
    conflicts: list[MemoryConflictEvidence] = Field(default_factory=list)
    ranking: RankingMetadata


class MemoryOperation(BaseModel):
    """One decision the extractor made about one fact.

    This type is the whole difference between memory and logging. An extractor
    that only ever returned ADD would produce a store that grows more wrong
    over time — "lives in Munich" and "moved to Berlin" both true, forever.
    """

    model_config = ConfigDict(extra="forbid")

    event: MemoryEvent
    content: str = Field(max_length=MEMORY_MAX_FACT_CHARS)
    target_id: uuid.UUID | None = None
    previous: str | None = None
    source_messages: tuple[MemorySourceReference, ...] = Field(
        max_length=MEMORY_MAX_WINDOW_MESSAGES
    )

    @model_validator(mode="after")
    def bounded_fact(self) -> "MemoryOperation":
        if _utf8_size(self.content) > MEMORY_MAX_FACT_BYTES:
            raise ValueError("Memory fact exceeds its byte limit.")
        return self


class MemoryOutcomeCounts(BaseModel):
    """Exact committed outcomes for one completely accepted operation plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    considered: int = Field(ge=0)
    added: int = Field(ge=0)
    updated: int = Field(ge=0)
    deleted: int = Field(ge=0)
    noop: int = Field(ge=0)
    failed: int = Field(ge=0)

    @model_validator(mode="after")
    def complete_partition(self) -> "MemoryOutcomeCounts":
        terminal = self.added + self.updated + self.deleted + self.noop + self.failed
        if terminal != self.considered:
            raise ValueError("Memory outcomes must partition every considered item.")
        return self

    @classmethod
    def from_operations(
        cls,
        operations: list["MemoryOperation"],
    ) -> "MemoryOutcomeCounts":
        return cls(
            considered=len(operations),
            added=sum(operation.event is MemoryEvent.ADD for operation in operations),
            updated=sum(
                operation.event is MemoryEvent.UPDATE for operation in operations
            ),
            deleted=sum(
                operation.event is MemoryEvent.DELETE for operation in operations
            ),
            noop=sum(operation.event is MemoryEvent.NOOP for operation in operations),
            failed=0,
        )

    @classmethod
    def one_failure(cls) -> "MemoryOutcomeCounts":
        return cls(
            considered=1,
            added=0,
            updated=0,
            deleted=0,
            noop=0,
            failed=1,
        )


class MemoryChange(BaseModel):
    """One entry in a memory's history.

    Event identity is append-only. When an agent says something surprising,
    the source must remain answerable; an owning-conversation erasure may clear
    retained before/after content without deleting the content-free event.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    memory_id: uuid.UUID
    event: MemoryEvent
    before: str | None
    after: str | None
    created_at: datetime
    scope: MemoryScope
    provenance: MemoryProvenance


class MemoryCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    semantic_search: bool = False
    keyword_search: bool = False
    infers_operations: bool = False
    history: bool = False


class MemoryError(Exception):
    """A memory operation failed."""

    def __init__(
        self, message: str, *, vendor: str | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.retryable = retryable


def require_memory_fact(value: str) -> str:
    """Return one bounded standalone fact or raise a stable domain failure."""
    normalized = value.strip()
    if not normalized:
        raise MemoryError("Nothing to remember.")
    if (
        len(normalized) > MEMORY_MAX_FACT_CHARS
        or _utf8_size(normalized) > MEMORY_MAX_FACT_BYTES
    ):
        raise MemoryError("Memory fact exceeds its limit.")
    return normalized


def require_memory_query(value: str) -> str:
    """Return one bounded recall query or raise a stable domain failure."""
    normalized = value.strip()
    if not normalized:
        raise MemoryError("Memory query is empty.")
    if (
        len(normalized) > MEMORY_MAX_QUERY_CHARS
        or _utf8_size(normalized) > MEMORY_MAX_QUERY_BYTES
    ):
        raise MemoryError("Memory query exceeds its limit.")
    return normalized
