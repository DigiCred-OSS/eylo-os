"""Telephony provider verification contracts for pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from eylo.modules.telephony.provider_config_domain import TelephonyProviderConfig


class TelephonyVerificationError(Exception):
    """Raised when bounded read-only carrier verification fails."""


@dataclass(frozen=True)
class TelephonyProviderVerification:
    provider: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TelephonyVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class TelephonyProviderVerifier(Protocol):
    async def verify(
        self,
        config: TelephonyProviderConfig,
    ) -> TelephonyProviderVerification: ...
