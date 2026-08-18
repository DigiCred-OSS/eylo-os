"""Sandbox verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from eylo.modules.sandbox_configs.domain import SandboxProviderConfig


class SandboxVerificationError(Exception):
    """The selected sandbox runtime failed bounded verification."""


@dataclass(frozen=True)
class SandboxVerificationEvidence:
    verified_image_id: str
    docker_server_version: str


@dataclass(frozen=True)
class SandboxVerificationResult:
    provider: str
    revision: int
    verified_at: datetime


class SandboxProviderVerifier(Protocol):
    async def verify(
        self,
        *,
        config: SandboxProviderConfig,
    ) -> SandboxVerificationEvidence: ...
