"""Filesystem storage constrained to a trusted, pipeline-derived root."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from eylo.sockets.storage.base import (
    StorageCapabilities,
    StorageObjectTooLarge,
    StorageOperationError,
    StorageVendorAdapter,
    StoredObject,
    UnsupportedStorageOperation,
    validate_content_sha256,
    validate_key,
    validate_limit,
)
from eylo.sockets.storage.schemas import FilesystemStorageConfig


class FilesystemStorageAdapter(StorageVendorAdapter):
    """Objects as files under one trusted organization namespace."""

    capabilities = StorageCapabilities(
        stable_key_put=True,
        put_reconciliation=True,
    )

    def __init__(self, config: FilesystemStorageConfig) -> None:
        self.config = config
        self._root = config.root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, key: str, *, allow_empty: bool = False) -> Path:
        normalized = validate_key(key, allow_empty=allow_empty)
        candidate = (self._root / normalized).resolve()
        if not candidate.is_relative_to(self._root):
            raise StorageOperationError("invalid_key", retryable=False)
        return candidate

    async def upload_file(
        self,
        *,
        path: Path,
        key: str,
        content_type: str = "application/octet-stream",
        content_sha256: str | None = None,
    ) -> str:
        del content_type
        destination = self._resolve(key)
        expected_digest = validate_content_sha256(content_sha256)

        def write() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if expected_digest is not None and _sha256_path(path) != expected_digest:
                raise StorageOperationError(
                    "upload_content_digest_mismatch",
                    retryable=False,
                )
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".eylo-upload-",
                dir=destination.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                shutil.copyfile(path, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            await asyncio.to_thread(write)
        except StorageOperationError:
            raise
        except OSError:
            raise StorageOperationError("upload_filesystem", retryable=True) from None
        return destination.as_uri()

    async def inspect_object(self, key: str) -> StoredObject | None:
        target = self._resolve(key)

        def inspect() -> StoredObject | None:
            if not target.is_file():
                return None
            return StoredObject(
                key=validate_key(key),
                size=target.stat().st_size,
                content_sha256=_sha256_path(target),
            )

        try:
            return await asyncio.to_thread(inspect)
        except OSError:
            raise StorageOperationError("inspect_filesystem", retryable=True) from None

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        del key, expires_in
        raise UnsupportedStorageOperation("presigned_download")

    async def list_objects(
        self,
        prefix: str,
        *,
        limit: int = 1000,
    ) -> list[StoredObject]:
        ceiling = validate_limit(limit)
        root = self._resolve(prefix, allow_empty=True) if prefix else self._root

        def walk() -> list[StoredObject]:
            if not root.exists():
                return []
            found: list[StoredObject] = []
            paths = sorted(root.rglob("*")) if root.is_dir() else [root]
            for path in paths:
                resolved = path.resolve()
                if not resolved.is_relative_to(self._root) or not resolved.is_file():
                    continue
                found.append(
                    StoredObject(
                        key=str(resolved.relative_to(self._root)),
                        size=resolved.stat().st_size,
                    )
                )
                if len(found) >= ceiling:
                    break
            return found

        try:
            return await asyncio.to_thread(walk)
        except OSError:
            raise StorageOperationError("list_filesystem", retryable=True) from None

    async def download_object(
        self,
        key: str,
        *,
        max_bytes: int | None = None,
    ) -> bytes | None:
        target = self._resolve(key)

        def read() -> bytes | None:
            if not target.is_file():
                return None
            if max_bytes is not None and target.stat().st_size > max_bytes:
                raise StorageObjectTooLarge
            return target.read_bytes()

        try:
            return await asyncio.to_thread(read)
        except StorageObjectTooLarge:
            raise
        except OSError:
            raise StorageOperationError("download_filesystem", retryable=True) from None

    async def delete_object(self, key: str) -> bool:
        target = self._resolve(key)

        def remove() -> None:
            target.unlink(missing_ok=True)

        try:
            await asyncio.to_thread(remove)
        except OSError:
            raise StorageOperationError("delete_filesystem", retryable=True) from None
        return True

    def build_object_url(self, key: str) -> str:
        return self._resolve(key).as_uri()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
