"""Memory provider policy and immutable resolved authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from eylo.modules.memory_configs.catalog import MemoryProviders
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)

__all__ = ["InvalidMemoryConfig", "MemoryProviderConfig", "ResolvedMemory"]

EMBEDDING_PROVIDER_CONFIG_ID_KEY = "embedding_provider_config_id"
LLM_PROVIDER_CONFIG_ID_KEY = "llm_provider_config_id"

_DEPENDENCY_CONFIG_FIELDS = frozenset(
    {EMBEDDING_PROVIDER_CONFIG_ID_KEY, LLM_PROVIDER_CONFIG_ID_KEY}
)
_ALLOWED_CONFIG_FIELDS = {
    MemoryProviders.PGVECTOR: _DEPENDENCY_CONFIG_FIELDS,
}
_REQUIRED_CONFIG_FIELDS = {
    MemoryProviders.PGVECTOR: tuple(sorted(_DEPENDENCY_CONFIG_FIELDS)),
}


class InvalidMemoryConfig(InvalidProviderConfig):
    """A memory provider config violates policy."""


@dataclass(frozen=True)
class MemoryProviderConfig:
    """Configured memory backend plus explicit embedding and LLM dependencies."""

    provider: MemoryProviders | str
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
        provider: MemoryProviders | str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> MemoryProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    @property
    def embedding_provider_config_id(self) -> UUID:
        return UUID(str(self.config[EMBEDDING_PROVIDER_CONFIG_ID_KEY]))

    @property
    def llm_provider_config_id(self) -> UUID:
        return UUID(str(self.config[LLM_PROVIDER_CONFIG_ID_KEY]))


@dataclass(frozen=True)
class ResolvedMemory:
    """One ready memory config revision and its verified dependency authority."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: MemoryProviders
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
            raise InvalidMemoryConfig("Resolved memory identifiers must be UUIDs.")
        if (
            isinstance(self.provider_config_revision, bool)
            or not isinstance(self.provider_config_revision, int)
            or self.provider_config_revision < 1
        ):
            raise InvalidMemoryConfig(
                "Resolved memory revision must be a positive integer."
            )
        if not all(
            isinstance(value, bool)
            for value in (self.configured, self.verified, self.ready, self.granted)
        ):
            raise InvalidMemoryConfig("Resolved memory flags must be booleans.")
        metadata = _validate_verification_metadata(
            self.verification_metadata,
            embedding_config_id=self.embedding_provider_config_id,
            llm_config_id=self.llm_provider_config_id,
        )
        object.__setattr__(
            self,
            "verification_metadata",
            MappingProxyType(metadata),
        )

    @classmethod
    def from_effective(
        cls,
        effective: EffectiveProviderConfig,
    ) -> ResolvedMemory:
        validated = MemoryProviderConfig.validate(
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
    def embedding_provider_config_id(self) -> UUID:
        return UUID(str(self.config[EMBEDDING_PROVIDER_CONFIG_ID_KEY]))

    @property
    def llm_provider_config_id(self) -> UUID:
        return UUID(str(self.config[LLM_PROVIDER_CONFIG_ID_KEY]))

    @property
    def embedding_provider_config_revision(self) -> int:
        return _metadata_revision(
            self.verification_metadata,
            "embedding_provider_config_revision",
        )

    @property
    def llm_provider_config_revision(self) -> int:
        return _metadata_revision(
            self.verification_metadata,
            "llm_provider_config_revision",
        )


def _provider(value: MemoryProviders | str) -> MemoryProviders:
    try:
        return value if isinstance(value, MemoryProviders) else MemoryProviders(value.strip().lower())
    except (AttributeError, ValueError):
        raise InvalidMemoryConfig(
            f"Unknown memory provider: {value}. "
            f"Available: {', '.join(provider.value for provider in MemoryProviders)}."
        ) from None


def _validate_config(
    provider: MemoryProviders,
    config: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidMemoryConfig("Config must be a mapping.")
    unknown = set(config) - _ALLOWED_CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidMemoryConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [field for field in _REQUIRED_CONFIG_FIELDS[provider] if field not in config]
    if missing:
        raise InvalidMemoryConfig(
            f"{provider.value} memory requires {missing} in config."
        )
    return {
        field: _uuid_string(config[field], field)
        for field in _REQUIRED_CONFIG_FIELDS[provider]
    }


def _uuid_string(value: object, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise InvalidMemoryConfig(f"{field_name} must be a UUID.") from None


def _validate_secrets(
    provider: MemoryProviders,
    secrets: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidMemoryConfig("Secrets must be a mapping.")
    if secrets:
        raise InvalidMemoryConfig(
            f"{provider.value} memory takes no secrets; its explicit embedding "
            "and LLM configs own their credentials."
        )
    return {}


def _metadata_revision(metadata: Mapping[str, object], field_name: str) -> int:
    value = metadata.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidMemoryConfig(
            f"Verified memory authority is missing {field_name}."
        )
    return value


def _validate_verification_metadata(
    metadata: Mapping[str, object],
    *,
    embedding_config_id: UUID,
    llm_config_id: UUID,
) -> dict[str, object]:
    if not isinstance(metadata, Mapping):
        raise InvalidMemoryConfig("Memory verification metadata must be a mapping.")
    values = dict(metadata)
    try:
        recorded_embedding_id = UUID(str(values["embedding_provider_config_id"]))
        recorded_llm_id = UUID(str(values["llm_provider_config_id"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise InvalidMemoryConfig(
            "Verified memory authority is missing dependency identity."
        ) from None
    if recorded_embedding_id != embedding_config_id or recorded_llm_id != llm_config_id:
        raise InvalidMemoryConfig(
            "Verified memory dependency identity does not match its config."
        )
    _metadata_revision(values, "embedding_provider_config_revision")
    _metadata_revision(values, "llm_provider_config_revision")
    dimensions = values.get("embedding_dimensions")
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
        raise InvalidMemoryConfig(
            "Verified memory authority has invalid embedding dimensions."
        )
    semantic_options = values.get("embedding_semantic_options")
    if not isinstance(semantic_options, Mapping):
        raise InvalidMemoryConfig(
            "Verified memory authority has invalid embedding semantic options."
        )
    values["embedding_semantic_options"] = dict(semantic_options)
    for field_name in (
        "embedding_provider",
        "embedding_endpoint",
        "embedding_model",
        "embedding_space_id",
        "llm_provider",
        "llm_model",
    ):
        value = values.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise InvalidMemoryConfig(
                f"Verified memory authority is missing {field_name}."
            )
    return values
