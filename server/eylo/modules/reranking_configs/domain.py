"""Provider-specific validation and immutable reranking runtime authority."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)
from eylo.modules.reranking_configs.catalog import (
    BEDROCK_RERANKING_MODELS,
    BEDROCK_RERANKING_REGIONS,
    RerankingProviders,
)

__all__ = [
    "InvalidRerankingConfig",
    "RerankingEndpointPolicy",
    "RerankingProviderConfig",
    "ResolvedReranking",
]

COHERE_API_URL = "https://api.cohere.com/v2/rerank"
VOYAGE_API_URL = "https://api.voyageai.com/v1/rerank"

_CONFIG_FIELDS = {
    RerankingProviders.BEDROCK: frozenset({"model", "region"}),
    RerankingProviders.COHERE: frozenset({"model", "base_url"}),
    RerankingProviders.VOYAGE: frozenset({"model"}),
}
_SECRET_FIELDS = {
    RerankingProviders.BEDROCK: frozenset(
        {"access_key_id", "secret_access_key", "session_token"}
    ),
    RerankingProviders.COHERE: frozenset({"api_key"}),
    RerankingProviders.VOYAGE: frozenset({"api_key"}),
}

_AWS_REGION = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")


class InvalidRerankingConfig(InvalidProviderConfig):
    """Raised when a reranking provider config violates policy."""


@dataclass(frozen=True)
class RerankingEndpointPolicy:
    """Deployment-owned exact compatible endpoints trusted with org data/keys."""

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
            raise InvalidRerankingConfig(
                "base_url is not trusted by this deployment. Add the exact URL "
                "to RERANKING_BASE_URL_ALLOWLIST before storing org credentials."
            )
        return normalized


@dataclass(frozen=True)
class RerankingProviderConfig:
    """Validated reranking config with plaintext secrets held in memory only."""

    provider: RerankingProviders | str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)
    endpoint_policy: RerankingEndpointPolicy = field(
        default_factory=RerankingEndpointPolicy,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        provider_value = (
            self.provider.value
            if isinstance(self.provider, RerankingProviders)
            else str(self.provider).strip().lower()
        )
        try:
            provider = RerankingProviders(provider_value)
        except ValueError:
            raise InvalidRerankingConfig(
                f"Unknown reranking provider: {self.provider}. Available: "
                f"{', '.join(item.value for item in RerankingProviders)}."
            ) from None
        if not isinstance(self.endpoint_policy, RerankingEndpointPolicy):
            raise InvalidRerankingConfig("Reranking endpoint policy is invalid.")
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
        endpoint_policy: RerankingEndpointPolicy | None = None,
    ) -> RerankingProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
            endpoint_policy=endpoint_policy or RerankingEndpointPolicy(),
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
        if self.provider is RerankingProviders.COHERE:
            return self.base_url or COHERE_API_URL
        if self.provider is RerankingProviders.VOYAGE:
            return VOYAGE_API_URL
        return _bedrock_endpoint(self.region)

    @property
    def region(self) -> str:
        return str(self.config["region"])

    def secret(self, name: str) -> str:
        return self.secrets[name]

    def optional_secret(self, name: str) -> str | None:
        return self.secrets.get(name)


def _validate_config(
    provider: RerankingProviders,
    config: Mapping[str, object],
    endpoint_policy: RerankingEndpointPolicy,
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidRerankingConfig("Config must be a mapping.")
    unknown = set(config) - _CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidRerankingConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    model = _required_string(config.get("model"), "model", maximum=255)
    if provider is RerankingProviders.BEDROCK:
        if model not in BEDROCK_RERANKING_MODELS:
            raise InvalidRerankingConfig(
                "model is not a supported AWS Bedrock reranking model."
            )
        region = _required_string(config.get("region"), "region", maximum=64)
        if not _AWS_REGION.fullmatch(region):
            raise InvalidRerankingConfig("region is not a valid AWS region name.")
        if region not in BEDROCK_RERANKING_REGIONS[model]:
            raise InvalidRerankingConfig(
                "model is not available for reranking in the configured region."
            )
        return {"model": model, "region": region}
    normalized: dict[str, object] = {"model": model}
    if provider is RerankingProviders.COHERE and config.get("base_url") is not None:
        normalized["base_url"] = endpoint_policy.require_allowed(config["base_url"])
    return normalized


def _validate_secrets(
    provider: RerankingProviders,
    secrets: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidRerankingConfig("Secrets must be a mapping.")
    unknown = set(secrets) - _SECRET_FIELDS[provider]
    if unknown:
        raise InvalidRerankingConfig(
            f"Unknown secret fields for {provider.value}: {sorted(unknown)}"
        )
    if provider is not RerankingProviders.BEDROCK:
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


def _required_string(value: object, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidRerankingConfig(f"{field_name} must be a string.")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(character in normalized for character in ("\x00", "\r", "\n"))
    ):
        raise InvalidRerankingConfig(
            f"{field_name} must be a non-empty single-line string of at most "
            f"{maximum} characters."
        )
    return normalized


def _normalize_http_url(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise InvalidRerankingConfig(
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
        raise InvalidRerankingConfig(
            f"{field_name} must be an HTTP(S) URL without credentials, query, or fragment."
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _bedrock_endpoint(region: str) -> str:
    return f"https://bedrock-agent-runtime.{region}.amazonaws.com"


@dataclass(frozen=True)
class ResolvedReranking:
    """Immutable resolved reranking authority with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: RerankingProviders
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
        endpoint_policy: RerankingEndpointPolicy | None = None,
    ) -> ResolvedReranking:
        validated = RerankingProviderConfig.validate(
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
        if self.provider is RerankingProviders.COHERE:
            return self.base_url or COHERE_API_URL
        if self.provider is RerankingProviders.VOYAGE:
            return VOYAGE_API_URL
        return _bedrock_endpoint(self.region)

    @property
    def region(self) -> str:
        return str(self.config["region"])

    def secret(self, name: str) -> str:
        return self.secrets[name]

    def optional_secret(self, name: str) -> str | None:
        return self.secrets.get(name)
