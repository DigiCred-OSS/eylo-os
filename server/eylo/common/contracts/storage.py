"""Immutable storage authority and object locator contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import quote
from uuid import UUID

_PROVIDER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class InvalidStorageLocator(ValueError):
    """A persisted storage authority or key is incomplete or malformed."""


@dataclass(frozen=True)
class StorageAuthority:
    organization_id: UUID
    provider_config_id: UUID
    provider_config_revision: int
    provider: str
    location: Mapping[str, str]

    def __post_init__(self) -> None:
        try:
            organization_id = UUID(str(self.organization_id))
            provider_config_id = UUID(str(self.provider_config_id))
        except ValueError:
            raise InvalidStorageLocator(
                "Storage authority identifiers must be UUIDs."
            ) from None
        revision = self.provider_config_revision
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise InvalidStorageLocator(
                "Storage provider config revision must be a positive integer."
            )
        provider = self.provider.strip().lower() if isinstance(self.provider, str) else ""
        if not _PROVIDER_PATTERN.fullmatch(provider):
            raise InvalidStorageLocator("Storage provider is invalid.")
        if not isinstance(self.location, Mapping) or not self.location:
            raise InvalidStorageLocator("Storage authority location is required.")
        location = {}
        for name, value in self.location.items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(value, str)
                or not value
            ):
                raise InvalidStorageLocator(
                    "Storage authority location must contain non-empty strings."
                )
            location[name] = value
        object.__setattr__(self, "organization_id", organization_id)
        object.__setattr__(self, "provider_config_id", provider_config_id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "location", MappingProxyType(location))

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            dict(self.location),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]

    def locate(self, key: str) -> StorageLocator:
        return StorageLocator(authority=self, key=key)

    def to_dict(self) -> dict[str, object]:
        return {
            "organization_id": str(self.organization_id),
            "provider_config_id": str(self.provider_config_id),
            "provider_config_revision": self.provider_config_revision,
            "provider": self.provider,
            "location": dict(self.location),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StorageAuthority:
        try:
            return cls(
                organization_id=UUID(str(value["organization_id"])),
                provider_config_id=UUID(str(value["provider_config_id"])),
                provider_config_revision=int(value["provider_config_revision"]),
                provider=str(value["provider"]),
                location=value["location"],
            )
        except (KeyError, TypeError, ValueError):
            raise InvalidStorageLocator("Storage authority is incomplete.") from None


@dataclass(frozen=True)
class StorageLocator:
    authority: StorageAuthority
    key: str

    def __post_init__(self) -> None:
        if not isinstance(self.authority, StorageAuthority):
            raise InvalidStorageLocator("Storage locator authority is invalid.")
        if (
            not isinstance(self.key, str)
            or not self.key
            or self.key.startswith("/")
            or "\x00" in self.key
            or any(part in {".", ".."} for part in self.key.replace("\\", "/").split("/"))
        ):
            raise InvalidStorageLocator("Storage object key is invalid.")

    @property
    def uri(self) -> str:
        authority = self.authority
        return (
            f"storage://{authority.provider}/{authority.organization_id}/"
            f"{authority.provider_config_id}@{authority.provider_config_revision}/"
            f"{authority.fingerprint}/{quote(self.key, safe='/')}"
        )

    def to_dict(self) -> dict[str, object]:
        return {**self.authority.to_dict(), "key": self.key}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StorageLocator:
        try:
            key = str(value["key"])
        except (KeyError, TypeError, ValueError):
            raise InvalidStorageLocator("Storage object key is missing.") from None
        return cls(authority=StorageAuthority.from_dict(value), key=key)
