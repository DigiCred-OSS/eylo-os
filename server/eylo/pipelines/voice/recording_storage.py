"""Voice recording operations over immutable storage locators."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from eylo.common.contracts.storage import StorageLocator
from eylo.common.database import start_transaction
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.storage.runtime import (
    StorageRuntime,
    resolve_storage_runtime_for_authority,
)
from eylo.sockets.storage.base import UnsupportedStorageOperation

logger = logging.getLogger(__name__)


class RecordingStorageUnavailable(Exception):
    """A recording object could not be addressed through its pinned authority."""


class RecordingObjectNotFound(RecordingStorageUnavailable):
    """The canonical recording row points at an object that is not present."""


@dataclass(frozen=True, slots=True)
class RecordingObjectStream:
    content: AsyncIterator[bytes]
    size: int
    content_type: str = "audio/wav"


async def upload_recording_path(
    *,
    runtime: StorageRuntime,
    path: Path,
    key: str,
    content_type: str = "audio/wav",
    content_sha256: str | None = None,
) -> StorageLocator:
    await runtime.adapter.upload_file(
        path=path,
        key=key,
        content_type=content_type,
        content_sha256=content_sha256,
    )
    return runtime.locate(key)


async def delete_recording_object(locator: StorageLocator) -> bool:
    """Delete from the exact authority that originally accepted the object."""
    try:
        async with start_transaction(ro=True):
            runtime = await resolve_storage_runtime_for_authority(locator.authority)
        return await runtime.adapter.delete_object(locator.key)
    except NotConfiguredError:
        logger.warning(
            "Pinned recording deletion authority is unavailable.",
        )
        return False
    except Exception as error:
        logger.error(
            "Recording object deletion failed: %s",
            type(error).__name__,
        )
        return False


async def generate_presigned_url(
    locator: StorageLocator,
    *,
    expires_in: int,
) -> str | None:
    """Generate a URL through the pinned authority; None means unsupported."""
    try:
        async with start_transaction(ro=True):
            runtime = await resolve_storage_runtime_for_authority(locator.authority)
        return await runtime.adapter.generate_presigned_url(
            locator.key,
            expires_in=expires_in,
        )
    except UnsupportedStorageOperation:
        logger.info(
            "Storage provider %s does not support presigned downloads.",
            locator.authority.provider,
        )
        return None
    except Exception as error:
        raise RecordingStorageUnavailable(
            "Recording download authority is unavailable."
        ) from error


async def open_recording_stream(locator: StorageLocator) -> RecordingObjectStream:
    """Open an authenticated application-proxied recording download."""
    try:
        async with start_transaction(ro=True):
            runtime = await resolve_storage_runtime_for_authority(locator.authority)
        stored = await runtime.adapter.inspect_object(locator.key)
        if stored is None:
            raise RecordingObjectNotFound("Recording object was not found.")
        return RecordingObjectStream(
            content=runtime.adapter.stream_object(locator.key),
            size=stored.size,
        )
    except RecordingObjectNotFound:
        raise
    except Exception as error:
        raise RecordingStorageUnavailable(
            "Recording download authority is unavailable."
        ) from error


__all__ = [
    "RecordingObjectNotFound",
    "RecordingObjectStream",
    "RecordingStorageUnavailable",
    "delete_recording_object",
    "generate_presigned_url",
    "open_recording_stream",
    "upload_recording_path",
]
