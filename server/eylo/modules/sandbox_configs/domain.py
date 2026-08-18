"""Sandbox provider policy and immutable resolved authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)
from eylo.modules.sandbox_configs.catalog import SandboxProviders

__all__ = ["InvalidSandboxConfig", "SandboxProviderConfig", "ResolvedSandbox"]

_CONFIG_FIELDS = (
    "endpoint",
    "image",
    "memory_mb",
    "cpu_cores",
    "disk_mb",
    "pids",
    "ttl_seconds",
    "command_timeout_seconds",
    "max_output_bytes",
    "max_sessions",
    "network",
)
_ALLOWED_CONFIG_FIELDS = {
    SandboxProviders.DOCKER: frozenset(_CONFIG_FIELDS),
}
_REQUIRED_CONFIG_FIELDS = {
    SandboxProviders.DOCKER: _CONFIG_FIELDS,
}


class InvalidSandboxConfig(InvalidProviderConfig):
    """A sandbox provider config violates policy."""


@dataclass(frozen=True)
class SandboxProviderConfig:
    """Explicit Docker location, image, and hard execution ceilings."""

    provider: SandboxProviders | str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        provider = _provider(self.provider)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "config",
            MappingProxyType(_validate_config(provider, self.config)),
        )
        object.__setattr__(
            self,
            "secrets",
            MappingProxyType(_validate_secrets(provider, self.secrets)),
        )

    @classmethod
    def validate(
        cls,
        *,
        provider: SandboxProviders | str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> SandboxProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )


@dataclass(frozen=True)
class ResolvedSandbox:
    """One ready sandbox config revision selected for executable work."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: SandboxProviders
    config: Mapping[str, object]
    verification_metadata: Mapping[str, object]
    configured: bool
    verified: bool
    ready: bool
    granted: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.provider_config_id, UUID)
            or not isinstance(self.organization_id, UUID)
        ):
            raise InvalidSandboxConfig("Resolved sandbox identifiers must be UUIDs.")
        if (
            isinstance(self.provider_config_revision, bool)
            or not isinstance(self.provider_config_revision, int)
            or self.provider_config_revision < 1
        ):
            raise InvalidSandboxConfig(
                "Resolved sandbox revision must be a positive integer."
            )
        if not all(
            isinstance(value, bool)
            for value in (self.configured, self.verified, self.ready, self.granted)
        ):
            raise InvalidSandboxConfig("Resolved sandbox flags must be booleans.")
        metadata = _validate_verification_metadata(
            self.verification_metadata,
            endpoint=str(self.config["endpoint"]),
            image=str(self.config["image"]),
        )
        object.__setattr__(
            self,
            "verification_metadata",
            MappingProxyType(metadata),
        )

    @classmethod
    def from_effective(cls, effective: EffectiveProviderConfig) -> ResolvedSandbox:
        validated = SandboxProviderConfig.validate(
            provider=effective.provider,
            config=effective.settings,
            secrets=effective.secrets,
        )
        return cls(
            provider_config_id=effective.provider_config_id,
            provider_config_revision=effective.revision,
            organization_id=effective.organization_id,
            provider=validated.provider,
            config=validated.config,
            verification_metadata=effective.verification_metadata,
            configured=effective.configured,
            verified=effective.verified,
            ready=effective.ready,
            granted=effective.granted,
        )

    @property
    def endpoint(self) -> str:
        return str(self.config["endpoint"])

    @property
    def verified_image_id(self) -> str:
        return str(self.verification_metadata["verified_image_id"])

    @property
    def max_sessions(self) -> int:
        return int(self.config["max_sessions"])

    def manifest(self, *, session_id: UUID, **overrides):
        """Build a manifest whose ceilings cannot be widened by a caller."""
        from eylo.common.contracts.sandbox import SandboxManifest

        fields = dict(overrides)
        fields.update(
            {
                "id": session_id,
                "image": self.verified_image_id,
                "network": False,
                "memory_mb": int(self.config["memory_mb"]),
                "cpu_cores": float(self.config["cpu_cores"]),
                "disk_mb": int(self.config["disk_mb"]),
                "pids": int(self.config["pids"]),
                "ttl_seconds": int(self.config["ttl_seconds"]),
                "command_timeout_seconds": int(
                    self.config["command_timeout_seconds"]
                ),
                "max_output_bytes": int(self.config["max_output_bytes"]),
            }
        )
        return SandboxManifest(**fields)


def _provider(value: SandboxProviders | str) -> SandboxProviders:
    try:
        return (
            value
            if isinstance(value, SandboxProviders)
            else SandboxProviders(value.strip().lower())
        )
    except (AttributeError, ValueError):
        raise InvalidSandboxConfig(
            f"Unknown sandbox provider: {value}. Available: "
            f"{', '.join(provider.value for provider in SandboxProviders)}."
        ) from None


def _validate_config(
    provider: SandboxProviders,
    config: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidSandboxConfig("Config must be a mapping.")
    unknown = set(config) - _ALLOWED_CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidSandboxConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field for field in _REQUIRED_CONFIG_FIELDS[provider] if field not in config
    ]
    if missing:
        raise InvalidSandboxConfig(
            f"{provider.value} sandbox requires explicit {missing}; no endpoint, "
            "image, resource limit, or network posture is defaulted."
        )

    endpoint = _text(config["endpoint"], "endpoint", max_length=512)
    if not endpoint.startswith("unix:///"):
        raise InvalidSandboxConfig(
            "Docker endpoint must be an explicit absolute unix:// socket. "
            "Remote daemon credentials and host environment discovery are unsupported."
        )
    image = _text(config["image"], "image", max_length=512)
    memory_mb = _integer(config["memory_mb"], "memory_mb", 64, 16384)
    disk_mb = _integer(config["disk_mb"], "disk_mb", 64, 16384)
    if disk_mb > memory_mb:
        raise InvalidSandboxConfig(
            "disk_mb cannot exceed memory_mb because Docker V1 enforces the "
            "workspace ceiling with tmpfs."
        )
    network = config["network"]
    if network is not False:
        raise InvalidSandboxConfig(
            "Docker V1 requires network=false. Unrestricted bridge egress cannot "
            "enforce Eylo's destination policy."
        )
    return {
        "endpoint": endpoint,
        "image": image,
        "memory_mb": memory_mb,
        "cpu_cores": _number(config["cpu_cores"], "cpu_cores", 0, 8),
        "disk_mb": disk_mb,
        "pids": _integer(config["pids"], "pids", 8, 4096),
        "ttl_seconds": _integer(config["ttl_seconds"], "ttl_seconds", 60, 86400),
        "command_timeout_seconds": _integer(
            config["command_timeout_seconds"],
            "command_timeout_seconds",
            1,
            3600,
        ),
        "max_output_bytes": _integer(
            config["max_output_bytes"],
            "max_output_bytes",
            1024,
            10 * 1024 * 1024,
        ),
        "max_sessions": _integer(config["max_sessions"], "max_sessions", 1, 100),
        "network": False,
    }


def _text(value: object, field_name: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidSandboxConfig(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized or len(normalized) > max_length or any(
        ord(character) < 32 for character in normalized
    ):
        raise InvalidSandboxConfig(f"{field_name} is invalid.")
    return normalized


def _integer(value: object, field_name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidSandboxConfig(
            f"{field_name} must be an integer between {low} and {high}; got {value!r}."
        )
    return value


def _number(
    value: object,
    field_name: str,
    low_exclusive: float,
    high: float,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not low_exclusive < value <= high
    ):
        raise InvalidSandboxConfig(
            f"{field_name} must be greater than {low_exclusive} and at most "
            f"{high}; got {value!r}."
        )
    return float(value)


def _validate_secrets(
    provider: SandboxProviders,
    secrets: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidSandboxConfig("Secrets must be a mapping.")
    if secrets:
        raise InvalidSandboxConfig(
            f"{provider.value} sandbox takes no secrets. Remote daemon "
            "credentials are unsupported."
        )
    return {}


def _validate_verification_metadata(
    metadata: Mapping[str, object],
    *,
    endpoint: str,
    image: str,
) -> dict[str, object]:
    if not isinstance(metadata, Mapping):
        raise InvalidSandboxConfig(
            "Sandbox verification metadata must be a mapping."
        )
    values = dict(metadata)
    required = {
        "endpoint": endpoint,
        "configured_image": image,
        "network_mode": "none",
        "workspace_storage": "tmpfs",
    }
    if any(values.get(key) != value for key, value in required.items()):
        raise InvalidSandboxConfig(
            "Verified sandbox authority does not match its endpoint, image, or policy."
        )
    for key in ("verified_image_id", "docker_server_version"):
        _text(values.get(key), key, max_length=512)
    return values
