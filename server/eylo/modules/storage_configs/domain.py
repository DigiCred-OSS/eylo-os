"""Provider-specific validation and resolved runtime values for storage configs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from uuid import UUID

from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)
from eylo.modules.storage_configs.catalog import StorageProviders

__all__ = [
    "InvalidStorageConfig",
    "ResolvedStorage",
    "S3CredentialMode",
    "StorageProviderConfig",
]

_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_REGION_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){2,4}$")
_NAMESPACE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IP_ADDRESS_PATTERN = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


class S3CredentialMode(str, Enum):
    STATIC = "static"
    SESSION = "session"


class InvalidStorageConfig(InvalidProviderConfig):
    """Raised when a storage provider config violates policy."""


@dataclass(frozen=True)
class StorageProviderConfig:
    """Validated storage config with plaintext secrets held in memory only."""

    provider: str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        provider_value = (
            self.provider.value
            if isinstance(self.provider, StorageProviders)
            else str(self.provider).lower().strip()
        )
        try:
            provider = StorageProviders(provider_value)
        except ValueError:
            raise InvalidStorageConfig(
                f"Unknown storage provider: {self.provider}"
            ) from None
        normalized_config = _validate_config(provider, self.config)
        normalized_secrets = _validate_secrets(
            provider,
            normalized_config,
            self.secrets,
        )
        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "config",
            MappingProxyType(normalized_config),
        )
        object.__setattr__(
            self,
            "secrets",
            MappingProxyType(normalized_secrets),
        )

    @classmethod
    def validate(
        cls,
        *,
        provider: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> StorageProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    def secret(self, name: str) -> str:
        return self.secrets[name]


def _validate_config(
    provider: StorageProviders,
    config: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidStorageConfig("Config must be a mapping.")
    if provider is StorageProviders.S3:
        return _validate_s3_config(config)
    if provider is StorageProviders.FILESYSTEM:
        return _validate_filesystem_config(config)
    raise InvalidStorageConfig(f"Unsupported storage provider: {provider.value}")


def _validate_s3_config(config: Mapping[str, object]) -> dict[str, object]:
    expected = frozenset({"bucket", "region", "credential_mode"})
    _require_exact_fields(config, expected, provider="s3")

    bucket = _required_string(config["bucket"], "bucket", maximum=63).lower()
    if (
        not _BUCKET_PATTERN.fullmatch(bucket)
        or ".." in bucket
        or _IP_ADDRESS_PATTERN.fullmatch(bucket)
        or bucket.startswith(("xn--", "sthree-", "amzn_s3_demo_"))
        or bucket.endswith("-s3alias")
    ):
        raise InvalidStorageConfig("bucket must be a valid AWS S3 bucket name.")

    region = _required_string(config["region"], "region", maximum=64).lower()
    if not _REGION_PATTERN.fullmatch(region):
        raise InvalidStorageConfig("region must be an explicit AWS region name.")

    try:
        credential_mode = S3CredentialMode(config["credential_mode"])
    except (TypeError, ValueError):
        raise InvalidStorageConfig(
            "credential_mode must be static or session."
        ) from None
    return {
        "bucket": bucket,
        "region": region,
        "credential_mode": credential_mode.value,
    }


def _validate_filesystem_config(
    config: Mapping[str, object],
) -> dict[str, object]:
    expected = frozenset({"namespace"})
    _require_exact_fields(config, expected, provider="filesystem")
    namespace = _required_string(
        config["namespace"],
        "namespace",
        maximum=128,
    )
    if namespace in {".", ".."} or not _NAMESPACE_PATTERN.fullmatch(namespace):
        raise InvalidStorageConfig(
            "namespace must use only letters, numbers, dot, underscore, or hyphen."
        )
    return {"namespace": namespace}


def _validate_secrets(
    provider: StorageProviders,
    config: Mapping[str, object],
    secrets: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidStorageConfig("Secrets must be a mapping.")
    if provider is StorageProviders.FILESYSTEM:
        if secrets:
            raise InvalidStorageConfig(
                "filesystem storage does not accept secret fields."
            )
        return {}

    expected = {"access_key_id", "secret_access_key"}
    if config["credential_mode"] == S3CredentialMode.SESSION.value:
        expected.add("session_token")
    _require_exact_fields(secrets, frozenset(expected), provider="s3 secrets")
    invalid = [
        field_name
        for field_name in expected
        if not isinstance(secrets[field_name], str) or not secrets[field_name].strip()
    ]
    if invalid:
        raise InvalidStorageConfig(
            f"s3 requires non-empty secret fields: {sorted(invalid)}"
        )
    return {field_name: secrets[field_name] for field_name in expected}


def _require_exact_fields(
    values: Mapping[str, object],
    expected: frozenset[str],
    *,
    provider: str,
) -> None:
    unknown = set(values) - expected
    if unknown:
        raise InvalidStorageConfig(
            f"Unknown config fields for {provider}: {sorted(unknown)}"
        )
    missing = expected - set(values)
    if missing:
        raise InvalidStorageConfig(
            f"{provider} requires fields: {sorted(missing)}"
        )


def _required_string(value: object, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise InvalidStorageConfig(
            f"{field_name} must be a non-empty string of at most {maximum} characters."
        )
    return value.strip()


@dataclass(frozen=True)
class ResolvedStorage:
    """Immutable resolved storage runtime value for one explicit revision."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: StorageProviders
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config_id: UUID,
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
    ) -> ResolvedStorage:
        validated = StorageProviderConfig.validate(
            provider=provider_config.provider,
            config=provider_config.settings,
            secrets=provider_config.secrets,
        )
        return cls(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config.revision,
            organization_id=organization_id,
            provider=validated.provider,
            config=validated.config,
            secrets=validated.secrets,
            configured=provider_config.configured,
            verified=provider_config.verified,
            ready=provider_config.ready,
            granted=provider_config.granted,
        )

    def secret(self, name: str) -> str:
        return self.secrets[name]
