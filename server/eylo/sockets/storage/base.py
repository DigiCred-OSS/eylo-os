"""Provider-neutral object-storage protocol and typed operation failures."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

_CONTENT_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class StorageOperationError(Exception):
    """One storage operation failed with a stable machine-readable outcome."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class UnsupportedStorageOperation(StorageOperationError):
    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"unsupported_{operation}", retryable=False)


class StorageObjectTooLarge(StorageOperationError):
    def __init__(self) -> None:
        super().__init__("object_too_large", retryable=False)


@dataclass(frozen=True)
class StorageCapabilities:
    upload: bool = True
    list: bool = True
    download: bool = True
    delete: bool = True
    presigned_download: bool = False
    stable_key_put: bool = False
    put_reconciliation: bool = False


@dataclass(frozen=True)
class StoredObject:
    """One bounded object observation, optionally with Eylo's content digest."""

    key: str
    size: int
    content_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("Stored object size cannot be negative.")
        if self.content_sha256 is not None and not _CONTENT_SHA256.fullmatch(
            self.content_sha256
        ):
            raise ValueError("Stored object content digest is invalid.")


class StorageVendorAdapter(ABC):
    """Operations implemented by one explicit storage authority."""

    capabilities = StorageCapabilities()

    @abstractmethod
    async def upload_file(
        self,
        *,
        path: Path,
        key: str,
        content_type: str = "application/octet-stream",
        content_sha256: str | None = None,
    ) -> str:
        """Put a local file at one stable key, or raise a typed failure."""

    @abstractmethod
    async def inspect_object(self, key: str) -> StoredObject | None:
        """Observe exact size/digest, or None only when the key does not exist."""

    @abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Return a bearer download URL, or raise unsupported/failure."""

    @abstractmethod
    async def list_objects(
        self,
        prefix: str,
        *,
        limit: int = 1000,
    ) -> list[StoredObject]:
        """Return at most ``limit`` objects under a prefix."""

    @abstractmethod
    async def download_object(
        self,
        key: str,
        *,
        max_bytes: int | None = None,
    ) -> bytes | None:
        """Return bytes or None only when the object does not exist."""

    async def stream_object(
        self,
        key: str,
        *,
        chunk_size: int = 64 * 1024,
    ) -> AsyncIterator[bytes]:
        """Stream one object; adapters may override to avoid buffering it."""
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise StorageOperationError("invalid_chunk_size", retryable=False)
        if not 1 <= chunk_size <= 8 * 1024 * 1024:
            raise StorageOperationError("invalid_chunk_size", retryable=False)
        content = await self.download_object(key)
        if content is None:
            return
        for start in range(0, len(content), chunk_size):
            yield content[start : start + chunk_size]

    @abstractmethod
    async def delete_object(self, key: str) -> bool:
        """Delete one object idempotently, or raise a typed failure."""


def validate_key(key: str, *, allow_empty: bool = False) -> str:
    if not isinstance(key, str):
        raise StorageOperationError("invalid_key", retryable=False)
    normalized = key.strip().replace("\\", "/")
    parts = normalized.split("/")
    if (
        (not allow_empty and not normalized)
        or normalized.startswith("/")
        or "\x00" in normalized
        or any(part in {".", ".."} for part in parts)
    ):
        raise StorageOperationError("invalid_key", retryable=False)
    return normalized


def validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
        raise StorageOperationError("invalid_limit", retryable=False)
    return limit


def validate_expiry(expires_in: int) -> int:
    if (
        isinstance(expires_in, bool)
        or not isinstance(expires_in, int)
        or not 1 <= expires_in <= 604800
    ):
        raise StorageOperationError("invalid_expiry", retryable=False)
    return expires_in


def validate_content_sha256(content_sha256: str | None) -> str | None:
    if content_sha256 is not None and not _CONTENT_SHA256.fullmatch(content_sha256):
        raise StorageOperationError("invalid_content_digest", retryable=False)
    return content_sha256
