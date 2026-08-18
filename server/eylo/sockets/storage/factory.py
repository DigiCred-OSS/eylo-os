"""Construct one storage adapter from one explicit typed runtime config."""

from __future__ import annotations

from eylo.sockets.storage.base import StorageVendorAdapter
from eylo.sockets.storage.filesystem import FilesystemStorageAdapter
from eylo.sockets.storage.s3 import S3StorageAdapter
from eylo.sockets.storage.schemas import (
    FilesystemStorageConfig,
    S3StorageConfig,
    StorageConfig,
)

__all__ = ["StorageFactory"]


class StorageFactory:
    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self._adapter = _build_adapter(config)

    def get_adapter(self) -> StorageVendorAdapter:
        return self._adapter


def _build_adapter(config: StorageConfig) -> StorageVendorAdapter:
    if isinstance(config, S3StorageConfig):
        return S3StorageAdapter(config)
    if isinstance(config, FilesystemStorageConfig):
        return FilesystemStorageAdapter(config)
    raise TypeError(f"Unsupported storage config type: {type(config).__name__}")
