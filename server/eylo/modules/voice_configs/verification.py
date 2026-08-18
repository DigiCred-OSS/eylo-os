"""Voice provider verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.domain import VoiceProviderConfig


class VoiceVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class VoiceProviderVerification:
    provider: str
    kind: VoiceKind


@dataclass(frozen=True)
class VoiceVerificationResult:
    provider: str
    kind: VoiceKind
    revision: int
    verified_at: datetime


class VoiceProviderVerifier(Protocol):
    """Port for one runtime-equivalent external provider check."""

    async def verify(
        self,
        config: VoiceProviderConfig,
    ) -> VoiceProviderVerification: ...
