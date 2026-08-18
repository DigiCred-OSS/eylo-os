"""Storage verification contracts shared with pipeline composition."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from eylo.modules.storage_configs.domain import StorageProviderConfig


class StorageVerificationError(Exception):
    """Raised when a provider cannot complete bounded live verification."""


@dataclass(frozen=True)
class StorageVerificationCapabilities:
    upload: bool
    list: bool
    download: bool
    delete: bool
    presigned_download: bool

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class StorageProviderVerification:
    provider: str
    capabilities: StorageVerificationCapabilities


@dataclass(frozen=True)
class StorageVerificationResult:
    provider: str
    revision: int
    verified_at: datetime
    capabilities: StorageVerificationCapabilities


class StorageProviderVerifier(Protocol):
    async def verify(
        self,
        config: StorageProviderConfig,
        *,
        organization_id: UUID,
        provider_config_id: UUID,
    ) -> StorageProviderVerification: ...
