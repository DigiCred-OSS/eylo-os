"""WebRTC provider verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.webrtc_configs.domain import WebRTCProviderConfig


class WebRTCVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class WebRTCProviderVerification:
    provider: str


@dataclass(frozen=True)
class WebRTCVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class WebRTCProviderVerifier(Protocol):
    """Port for one runtime-equivalent external provider check."""

    async def verify(
        self,
        config: WebRTCProviderConfig,
    ) -> WebRTCProviderVerification: ...
