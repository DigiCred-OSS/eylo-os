"""Email provider verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.email_configs.domain import EmailProviderConfig


class EmailVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class EmailProviderVerification:
    provider: str


@dataclass(frozen=True)
class EmailVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class EmailProviderVerifier(Protocol):
    async def verify(
        self,
        config: EmailProviderConfig,
    ) -> EmailProviderVerification: ...
