"""Storage providers and the concrete operations each implements."""

from __future__ import annotations

from enum import Enum

__all__ = ["StorageProviders", "storage_capabilities"]


class StorageProviders(str, Enum):
    S3 = "s3"
    FILESYSTEM = "filesystem"


def storage_capabilities(provider: str | StorageProviders) -> dict[str, bool]:
    try:
        selected = StorageProviders(provider)
    except ValueError:
        return {
            "upload": False,
            "list": False,
            "download": False,
            "delete": False,
            "presigned_download": False,
        }
    return {
        "upload": True,
        "list": True,
        "download": True,
        "delete": True,
        "presigned_download": selected is StorageProviders.S3,
    }
