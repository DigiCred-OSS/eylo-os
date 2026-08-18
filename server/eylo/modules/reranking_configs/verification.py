"""Reranking verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.reranking_configs.domain import RerankingProviderConfig


class RerankingVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class RerankingProviderVerification:
    provider: str


@dataclass(frozen=True)
class RerankingVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class RerankingProviderVerifier(Protocol):
    async def verify(
        self,
        config: RerankingProviderConfig,
    ) -> RerankingProviderVerification: ...
