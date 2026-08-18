"""Typed storage socket exports."""

from eylo.sockets.storage.base import (
    StorageCapabilities,
    StorageObjectTooLarge,
    StorageOperationError,
    StorageVendorAdapter,
    StoredObject,
    UnsupportedStorageOperation,
)
from eylo.sockets.storage.factory import StorageFactory

__all__ = [
    "StorageCapabilities",
    "StorageFactory",
    "StorageObjectTooLarge",
    "StorageOperationError",
    "StorageVendorAdapter",
    "StoredObject",
    "UnsupportedStorageOperation",
]
