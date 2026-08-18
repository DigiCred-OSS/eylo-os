"""Memory verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from eylo.modules.memory_configs.domain import MemoryProviderConfig


class MemoryVerificationError(Exception):
    """The composed memory runtime failed bounded verification."""


@dataclass(frozen=True)
class MemoryDependencyAuthority:
    embedding_provider_config_id: UUID
    embedding_provider_config_revision: int
    embedding_provider: str
    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    embedding_semantic_options: dict[str, object]
    embedding_space_id: str
    llm_provider_config_id: UUID
    llm_provider_config_revision: int
    llm_provider: str
    llm_model: str

    def to_metadata(self) -> dict[str, object]:
        return {
            "embedding_provider_config_id": str(self.embedding_provider_config_id),
            "embedding_provider_config_revision": self.embedding_provider_config_revision,
            "embedding_provider": self.embedding_provider,
            "embedding_endpoint": self.embedding_endpoint,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "embedding_semantic_options": dict(self.embedding_semantic_options),
            "embedding_space_id": self.embedding_space_id,
            "llm_provider_config_id": str(self.llm_provider_config_id),
            "llm_provider_config_revision": self.llm_provider_config_revision,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
        }


@dataclass(frozen=True)
class MemoryVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class MemoryProviderVerifier(Protocol):
    async def verify(
        self,
        *,
        organization_id: UUID,
        memory_config_id: UUID,
        memory_config_revision: int,
        config: MemoryProviderConfig,
        authority: MemoryDependencyAuthority,
        embedding_runtime,
        llm_runtime,
    ) -> None: ...
