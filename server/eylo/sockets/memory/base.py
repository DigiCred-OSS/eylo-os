"""Provider-neutral contracts for the `memory` socket."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from eylo.sockets.memory.schemas import (
    Memory,
    MemoryActor,
    MemoryCapabilities,
    MemoryChange,
    MemoryInputMessage,
    MemoryOperation,
    MemoryOrigin,
    MemoryProvenance,
    MemoryResult,
    MemoryScope,
    MemoryUpdateResult,
)


class MemoryVendorAdapter(ABC):
    """Store and retrieve facts inside exact authorized subject boundaries."""

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> MemoryCapabilities: ...

    @abstractmethod
    async def add(
        self,
        messages: list[MemoryInputMessage],
        *,
        scope: MemoryScope,
        source_conversation_id: UUID,
        origin: MemoryOrigin,
        actor: MemoryActor | None,
        metadata: dict[str, Any] | None = None,
        formation_job_id: UUID | None = None,
    ) -> list[MemoryOperation]:
        """Learn from a conversation."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        scopes: tuple[MemoryScope, ...],
        limit: int = 5,
    ) -> list[MemoryResult]:
        """Memories relevant to `query`, most relevant first.

        The complete authorized scope set is explicit. Vendors rank the union
        in one query; callers never concatenate independently ranked lists.
        """
        ...

    @abstractmethod
    async def get_all(self, *, scope: MemoryScope, limit: int = 100) -> list[Memory]:
        """Everything in scope, newest first. For operators, not for turns."""
        ...

    @abstractmethod
    async def update(
        self,
        memory_id: UUID,
        content: str,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> MemoryUpdateResult:
        """Correct one scoped memory, reporting whether durable state changed."""
        ...

    @abstractmethod
    async def expire(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> bool:
        """Remove one fact from recall while retaining its operator history."""
        ...

    @abstractmethod
    async def delete(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
        provenance: MemoryProvenance,
    ) -> bool:
        """Remove the current fact and vector. True when they are gone.

        The new deletion marker contains no fact content. Earlier ADD/UPDATE
        history can retain prior values until the owning conversation's
        explicit erasure workflow clears them.
        """
        ...

    @abstractmethod
    async def history(
        self,
        memory_id: UUID,
        *,
        scope: MemoryScope,
    ) -> list[MemoryChange]:
        """How this scoped memory came to say what it says."""
        ...
