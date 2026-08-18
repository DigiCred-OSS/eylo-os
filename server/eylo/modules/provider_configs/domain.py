"""Validate and represent revisioned provider configurations."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import UUID

import uuid_utils

from eylo.common.contracts.provider_config import Capability, ProviderConfigError
from eylo.modules.provider_configs.masking import apply_secret_patch

_PROVIDER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class InvalidProviderConfig(ProviderConfigError):
    """Raised when a provider configuration violates a domain invariant."""


class ProviderConfigNotFound(ProviderConfigError):
    """Raised when an active provider configuration is unavailable in an org."""


class ProviderConfigConflict(ProviderConfigError):
    """Raised when a provider configuration violates an active uniqueness rule."""


class ProviderConfigRevisionConflict(ProviderConfigConflict):
    """Raised when a stale operation targets a superseded config revision."""


@dataclass(frozen=True)
class EffectiveProviderConfig:
    """Immutable provider material resolved for one explicit capability use."""

    organization_id: UUID
    capability: Capability
    provider_config_id: UUID
    revision: int
    provider: str
    settings: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    verification_metadata: Mapping[str, object] = field(default_factory=dict)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, UUID) or not isinstance(
            self.provider_config_id, UUID
        ):
            raise InvalidProviderConfig(
                "Effective provider config identifiers must be UUIDs."
            )
        object.__setattr__(self, "capability", _validate_capability(self.capability))
        object.__setattr__(self, "provider", _normalize_provider(self.provider))
        object.__setattr__(self, "revision", _validate_revision(self.revision))
        object.__setattr__(
            self,
            "settings",
            MappingProxyType(_validate_config(self.settings)),
        )
        object.__setattr__(
            self,
            "secrets",
            MappingProxyType(_validate_secrets(self.secrets)),
        )
        object.__setattr__(
            self,
            "verification_metadata",
            MappingProxyType(_validate_config(self.verification_metadata)),
        )


@dataclass(frozen=True)
class ProviderConfig:
    """Provider configuration aggregate with plaintext secrets held in memory only."""

    id: UUID
    organization_id: UUID
    capability: Capability
    provider: str
    name: str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)
    deleted: bool = False
    revision: int = 1
    current_revision: int | None = None
    enabled: bool = True
    verified_at: datetime | None = None
    verification_metadata: Mapping[str, object] = field(default_factory=dict)
    credentials_available: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", _validate_capability(self.capability))
        object.__setattr__(self, "provider", _normalize_provider(self.provider))
        object.__setattr__(self, "name", _normalize_name(self.name))
        object.__setattr__(self, "config", _validate_config(self.config))
        object.__setattr__(self, "secrets", _validate_secrets(self.secrets))
        object.__setattr__(self, "revision", _validate_revision(self.revision))
        current_revision = (
            self.revision
            if self.current_revision is None
            else _validate_revision(self.current_revision)
        )
        if self.revision > current_revision:
            raise InvalidProviderConfig(
                "Selected revision cannot exceed the current revision."
            )
        object.__setattr__(self, "current_revision", current_revision)
        if not isinstance(self.enabled, bool):
            raise InvalidProviderConfig("Enabled must be a boolean.")
        if not isinstance(self.credentials_available, bool):
            raise InvalidProviderConfig("Credential availability must be a boolean.")
        object.__setattr__(
            self,
            "verified_at",
            _validate_verified_at(self.verified_at),
        )
        object.__setattr__(
            self,
            "verification_metadata",
            MappingProxyType(_validate_config(self.verification_metadata)),
        )

    @classmethod
    def create(
        cls,
        *,
        organization_id: UUID,
        capability: Capability | str,
        provider: str,
        name: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> "ProviderConfig":
        return cls(
            id=UUID(str(uuid_utils.uuid7())),
            organization_id=organization_id,
            capability=capability,
            provider=provider,
            name=name,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
            revision=1,
            current_revision=1,
            enabled=True,
            verified_at=None,
            verification_metadata={},
        )

    def update(
        self,
        *,
        name: str | None = None,
        config: Mapping[str, object] | None = None,
        secret_patch: Mapping[str, str | None] | None = None,
    ) -> "ProviderConfig":
        if not self.is_current:
            raise ProviderConfigRevisionConflict(
                "Only the current provider configuration revision can be updated."
            )
        next_revision = self.revision + 1
        return replace(
            self,
            name=self.name if name is None else name,
            config=self.config if config is None else config,
            secrets=(
                self.secrets
                if secret_patch is None
                else apply_secret_patch(self.secrets, secret_patch)
            ),
            revision=next_revision,
            current_revision=next_revision,
            verified_at=None,
            verification_metadata={},
        )

    def rename(self, name: str) -> "ProviderConfig":
        """Change display metadata without creating an executable revision."""
        if not self.is_current:
            raise ProviderConfigRevisionConflict(
                "Only the current provider configuration revision can be renamed."
            )
        return replace(self, name=name)

    @property
    def configured(self) -> bool:
        return self.credentials_available

    @property
    def verified(self) -> bool:
        return self.verified_at is not None

    @property
    def is_current(self) -> bool:
        return self.revision == self.current_revision

    @property
    def ready(self) -> bool:
        return (
            self.configured
            and self.verified
            and self.enabled
            and not self.deleted
            and self.is_current
        )

    def mark_verified(
        self,
        *,
        expected_revision: int,
        verified_at: datetime | None = None,
        verification_metadata: Mapping[str, object] | None = None,
    ) -> "ProviderConfig":
        if _validate_revision(expected_revision) != self.current_revision:
            raise ProviderConfigRevisionConflict(
                "Provider configuration changed during verification."
            )
        if not self.is_current:
            raise ProviderConfigRevisionConflict(
                "Only the current provider configuration revision can be verified."
            )
        return replace(
            self,
            verified_at=verified_at or datetime.now(timezone.utc),
            verification_metadata=(
                {} if verification_metadata is None else verification_metadata
            ),
        )

    def set_enabled(self, enabled: bool) -> "ProviderConfig":
        if not isinstance(enabled, bool):
            raise InvalidProviderConfig("Enabled must be a boolean.")
        return replace(self, enabled=enabled)

    def to_effective(self, *, granted: bool) -> EffectiveProviderConfig:
        if not isinstance(granted, bool):
            raise InvalidProviderConfig("Granted must be a boolean.")
        return EffectiveProviderConfig(
            organization_id=self.organization_id,
            capability=self.capability,
            provider_config_id=self.id,
            revision=self.revision,
            provider=self.provider,
            settings=self.config,
            secrets=self.secrets,
            verification_metadata=self.verification_metadata,
            configured=self.configured,
            verified=self.verified,
            ready=self.ready,
            granted=granted,
        )

    def soft_delete(self) -> "ProviderConfig":
        return replace(self, deleted=True, enabled=False)


def _validate_capability(value: Capability | str) -> Capability:
    try:
        return Capability(value)
    except ValueError as error:
        raise InvalidProviderConfig("Capability is not supported.") from error


def _normalize_provider(value: str) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    if not _PROVIDER_PATTERN.fullmatch(normalized):
        raise InvalidProviderConfig(
            "Provider must be a lowercase machine-readable identifier."
        )
    return normalized


def _normalize_name(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise InvalidProviderConfig("Name cannot be empty.")
    return normalized


def _validate_config(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise InvalidProviderConfig("Config must be a string-keyed mapping.")
    return dict(value)


def _validate_secrets(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) and isinstance(secret, str) and secret
        for key, secret in value.items()
    ):
        raise InvalidProviderConfig(
            "Secrets must be a string-keyed mapping of non-empty strings."
        )
    return dict(value)


def _validate_revision(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidProviderConfig("Revision must be a positive integer.")
    return value


def _validate_verified_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidProviderConfig("Verification time must be timezone-aware.")
    return value
