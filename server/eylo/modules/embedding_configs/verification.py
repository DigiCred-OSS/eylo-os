"""Embedding provider verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.embedding_configs.domain import EmbeddingProviderConfig


class EmbeddingVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class EmbeddingProviderVerification:
    provider: str
    dimensions: int


@dataclass(frozen=True)
class EmbeddingVerificationResult:
    provider: str
    revision: int
    dimensions: int
    verified_at: datetime


class EmbeddingProviderVerifier(Protocol):
    async def verify(
        self,
        config: EmbeddingProviderConfig,
    ) -> EmbeddingProviderVerification: ...
