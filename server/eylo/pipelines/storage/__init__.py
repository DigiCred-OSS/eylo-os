"""Storage runtime composition."""

from eylo.pipelines.storage.config import build_storage_runtime_config
from eylo.pipelines.storage.runtime import (
    StorageRuntime,
    resolve_storage_runtime_for_authority,
    resolve_storage_runtime_for_new,
)

__all__ = [
    "StorageRuntime",
    "build_storage_runtime_config",
    "resolve_storage_runtime_for_authority",
    "resolve_storage_runtime_for_new",
]
