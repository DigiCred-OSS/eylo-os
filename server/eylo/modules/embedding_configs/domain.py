"""Provider-specific validation and immutable embedding runtime authority."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from eylo.modules.embedding_configs.catalog import (
    BEDROCK_EMBEDDING_DIMENSIONS,
    BEDROCK_EMBEDDING_MODELS,
    EmbeddingProviders,
)
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)

__all__ = [
    "EmbeddingEndpointPolicy",
    "EmbeddingProviderConfig",
    "InvalidEmbeddingConfig",
    "ResolvedEmbedding",
]

OPENAI_API_BASE_URL = "https://api.openai.com/v1"
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

_CONFIG_FIELDS = {
    EmbeddingProviders.BEDROCK: frozenset(
        {"model", "region", "dimensions", "normalize"}
    ),
    EmbeddingProviders.OPENAI: frozenset({"model", "base_url"}),
    EmbeddingProviders.VOYAGE: frozenset({"model"}),
}
_SECRET_FIELDS = {
    EmbeddingProviders.BEDROCK: frozenset(
        {"access_key_id", "secret_access_key", "session_token"}
    ),
    EmbeddingProviders.OPENAI: frozenset({"api_key"}),
    EmbeddingProviders.VOYAGE: frozenset({"api_key"}),
}

_AWS_REGION = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")


class InvalidEmbeddingConfig(InvalidProviderConfig):
    """Raised when an embedding provider config violates policy."""


@dataclass(frozen=True)
class EmbeddingEndpointPolicy:
    """Deployment-owned exact custom endpoints trusted to receive org data/keys."""

    allowed_base_urls: Collection[str] = ()

    def __post_init__(self) -> None:
        normalized = frozenset(
            _normalize_http_url(value, field_name="allowed base URL")
            for value in self.allowed_base_urls
        )
        object.__setattr__(self, "allowed_base_urls", normalized)

    def require_allowed(self, value: object) -> str:
        normalized = _normalize_http_url(value, field_name="base_url")
        if normalized not in self.allowed_base_urls:
            raise InvalidEmbeddingConfig(
                "base_url is not trusted by this deployment. Add the exact URL "
                "to EMBEDDING_BASE_URL_ALLOWLIST before storing org credentials."
            )
        return normalized


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    """Validated embedding config with plaintext secrets held in memory only."""

    provider: EmbeddingProviders | str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)
    endpoint_policy: EmbeddingEndpointPolicy = field(
        default_factory=EmbeddingEndpointPolicy,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        provider_value = (
            self.provider.value
            if isinstance(self.provider, EmbeddingProviders)
            else str(self.provider).strip().lower()
        )
        try:
            provider = EmbeddingProviders(provider_value)
        except ValueError:
            raise InvalidEmbeddingConfig(
                f"Unknown embedding provider: {self.provider}. Available: "
                f"{', '.join(item.value for item in EmbeddingProviders)}."
            ) from None
        if not isinstance(self.endpoint_policy, EmbeddingEndpointPolicy):
            raise InvalidEmbeddingConfig("Embedding endpoint policy is invalid.")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "config",
            MappingProxyType(
                _validate_config(provider, self.config, self.endpoint_policy)
            ),
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
        provider: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
        endpoint_policy: EmbeddingEndpointPolicy | None = None,
    ) -> EmbeddingProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
            endpoint_policy=endpoint_policy or EmbeddingEndpointPolicy(),
        )

    @property
    def model(self) -> str:
        return str(self.config["model"])

    @property
    def base_url(self) -> str | None:
        value = self.config.get("base_url")
        return str(value) if value is not None else None

    @property
    def endpoint(self) -> str:
        if self.provider is EmbeddingProviders.OPENAI:
            return self.base_url or OPENAI_API_BASE_URL
        if self.provider is EmbeddingProviders.VOYAGE:
            return VOYAGE_API_URL
        return _bedrock_endpoint(self.region)

    @property
    def region(self) -> str:
        return str(self.config["region"])

    @property
    def requested_dimensions(self) -> int:
        return int(self.config["dimensions"])

    @property
    def normalize(self) -> bool:
        return bool(self.config["normalize"])

    def secret(self, name: str) -> str:
        return self.secrets[name]

    def optional_secret(self, name: str) -> str | None:
        return self.secrets.get(name)


def _validate_config(
    provider: EmbeddingProviders,
    config: Mapping[str, object],
    endpoint_policy: EmbeddingEndpointPolicy,
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidEmbeddingConfig("Config must be a mapping.")
    unknown = set(config) - _CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidEmbeddingConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    model = _required_string(config.get("model"), "model", maximum=255)
    if provider is EmbeddingProviders.BEDROCK:
        if model not in BEDROCK_EMBEDDING_MODELS:
            raise InvalidEmbeddingConfig(
                "model is not a supported AWS Bedrock embedding model."
            )
        region = _required_string(config.get("region"), "region", maximum=64)
        if not _AWS_REGION.fullmatch(region):
            raise InvalidEmbeddingConfig("region is not a valid AWS region name.")
        dimensions = _required_integer(config.get("dimensions"), "dimensions")
        if dimensions not in BEDROCK_EMBEDDING_DIMENSIONS:
            allowed = ", ".join(str(value) for value in BEDROCK_EMBEDDING_DIMENSIONS)
            raise InvalidEmbeddingConfig(f"dimensions must be one of: {allowed}.")
        normalize = config.get("normalize")
        if not isinstance(normalize, bool):
            raise InvalidEmbeddingConfig("normalize must be a boolean.")
        return {
            "model": model,
            "region": region,
            "dimensions": dimensions,
            "normalize": normalize,
        }
    normalized: dict[str, object] = {"model": model}
    if provider is EmbeddingProviders.OPENAI and config.get("base_url") is not None:
        normalized["base_url"] = endpoint_policy.require_allowed(config["base_url"])
    return normalized


def _validate_secrets(
    provider: EmbeddingProviders,
    secrets: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidEmbeddingConfig("Secrets must be a mapping.")
    expected = _SECRET_FIELDS[provider]
    unknown = set(secrets) - expected
    if unknown:
        raise InvalidEmbeddingConfig(
            f"Unknown secret fields for {provider.value}: {sorted(unknown)}"
        )
    if provider is not EmbeddingProviders.BEDROCK:
        return {
            "api_key": _required_string(
                secrets.get("api_key"),
                "api_key",
                maximum=8192,
            )
        }
    normalized = {
        "access_key_id": _required_string(
            secrets.get("access_key_id"),
            "access_key_id",
            maximum=512,
        ),
        "secret_access_key": _required_string(
            secrets.get("secret_access_key"),
            "secret_access_key",
            maximum=8192,
        ),
    }
    session_token = secrets.get("session_token")
    if session_token is not None:
        normalized["session_token"] = _required_string(
            session_token,
            "session_token",
            maximum=8192,
        )
    return normalized


def _required_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidEmbeddingConfig(f"{field_name} must be an integer.")
    return value


def _required_string(value: object, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidEmbeddingConfig(f"{field_name} must be a string.")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(character in normalized for character in ("\x00", "\r", "\n"))
    ):
        raise InvalidEmbeddingConfig(
            f"{field_name} must be a non-empty single-line string of at most "
            f"{maximum} characters."
        )
    return normalized


def _normalize_http_url(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise InvalidEmbeddingConfig(
            f"{field_name} must be a non-empty HTTP(S) URL of at most 2048 characters."
        )
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidEmbeddingConfig(
            f"{field_name} must be an HTTP(S) URL without credentials, query, or fragment."
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _bedrock_endpoint(region: str) -> str:
    return f"https://bedrock-runtime.{region}.amazonaws.com"


@dataclass(frozen=True)
class ResolvedEmbedding:
    """Immutable resolved embedding authority with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: EmbeddingProviders
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    verification_metadata: Mapping[str, object] = field(default_factory=dict)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))
        object.__setattr__(self, "secrets", MappingProxyType(dict(self.secrets)))
        object.__setattr__(
            self,
            "verification_metadata",
            MappingProxyType(dict(self.verification_metadata)),
        )

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config_id: UUID,
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
        endpoint_policy: EmbeddingEndpointPolicy | None = None,
    ) -> ResolvedEmbedding:
        validated = EmbeddingProviderConfig.validate(
            provider=provider_config.provider,
            config=provider_config.settings,
            secrets=provider_config.secrets,
            endpoint_policy=endpoint_policy,
        )
        return cls(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config.revision,
            organization_id=organization_id,
            provider=validated.provider,
            config=validated.config,
            secrets=validated.secrets,
            verification_metadata=provider_config.verification_metadata,
            configured=provider_config.configured,
            verified=provider_config.verified,
            ready=provider_config.ready,
            granted=provider_config.granted,
        )

    @property
    def model(self) -> str:
        return str(self.config["model"])

    @property
    def base_url(self) -> str | None:
        value = self.config.get("base_url")
        return str(value) if value is not None else None

    @property
    def endpoint(self) -> str:
        if self.provider is EmbeddingProviders.OPENAI:
            return self.base_url or OPENAI_API_BASE_URL
        if self.provider is EmbeddingProviders.VOYAGE:
            return VOYAGE_API_URL
        return _bedrock_endpoint(self.region)

    @property
    def region(self) -> str:
        return str(self.config["region"])

    @property
    def requested_dimensions(self) -> int:
        return int(self.config["dimensions"])

    @property
    def normalize(self) -> bool:
        return bool(self.config["normalize"])

    @property
    def dimensions(self) -> int:
        value = self.verification_metadata.get("dimensions")
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise InvalidEmbeddingConfig(
                "Verified embedding config is missing its observed dimensions."
            )
        return value

    def secret(self, name: str) -> str:
        return self.secrets[name]

    def optional_secret(self, name: str) -> str | None:
        return self.secrets.get(name)
