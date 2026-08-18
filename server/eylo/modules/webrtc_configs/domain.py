"""Provider-specific validation and resolved runtime values for WebRTC configs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
from uuid import UUID

from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)
from eylo.modules.webrtc_configs.catalog import WebRTCProviders

__all__ = ["InvalidWebRTCConfig", "ResolvedWebRTC", "WebRTCProviderConfig"]

_SECRET_FIELD_NAME = "api_key"
_METERED_DOMAIN_SUFFIX = ".metered.live"
_METERED_APP_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$")

_COMMON_CONFIG_FIELDS = frozenset({"timeout", "max_retries", "retry_delay"})
_CONFIG_FIELDS = {
    WebRTCProviders.METERED: _COMMON_CONFIG_FIELDS | {"app_name"},
    WebRTCProviders.TURNIX: _COMMON_CONFIG_FIELDS
    | {
        "initiator_client",
        "receiver_client",
        "room",
        "ttl",
        "preferred_region",
        "fixed_region",
        "client_ip",
    },
}
_REQUIRED_CONFIG_FIELDS = {
    WebRTCProviders.METERED: frozenset({"app_name"}),
    WebRTCProviders.TURNIX: frozenset(),
}


class InvalidWebRTCConfig(InvalidProviderConfig):
    """Raised when a WebRTC provider config violates policy."""


@dataclass(frozen=True)
class WebRTCProviderConfig:
    """Validated WebRTC provider config with plaintext secrets in memory only."""

    provider: str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        provider_value = str(self.provider).lower().strip()
        try:
            provider = WebRTCProviders(provider_value)
        except ValueError:
            raise InvalidWebRTCConfig(
                f"Unknown WebRTC provider: {self.provider}"
            ) from None
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "config", _validate_config(self.config, provider))
        object.__setattr__(self, "secrets", _validate_secrets(self.secrets, provider))

    @classmethod
    def validate(
        cls,
        *,
        provider: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> WebRTCProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    @property
    def secret(self) -> str:
        return self.secrets[_SECRET_FIELD_NAME]


def _validate_config(
    config: Mapping[str, object],
    provider: WebRTCProviders,
) -> Mapping[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidWebRTCConfig("Config must be a mapping.")
    unknown = set(config) - _CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidWebRTCConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field_name
        for field_name in _REQUIRED_CONFIG_FIELDS[provider]
        if not _is_configured_value(config.get(field_name))
    ]
    if missing:
        raise InvalidWebRTCConfig(
            f"Provider {provider.value} requires config fields: {missing}"
        )
    validated = dict(config)
    if provider is WebRTCProviders.METERED:
        validated["app_name"] = _normalize_metered_app_name(config["app_name"])
    _validate_number(config, "timeout", minimum=0, maximum=30, inclusive_minimum=False)
    _validate_integer(config, "max_retries", minimum=0, maximum=5)
    _validate_number(config, "retry_delay", minimum=0, maximum=10)
    if provider is WebRTCProviders.TURNIX:
        _validate_integer(config, "ttl", minimum=1, maximum=86_400)
        for field_name in (
            "initiator_client",
            "receiver_client",
            "room",
            "preferred_region",
            "fixed_region",
        ):
            _validate_optional_string(config, field_name)
        client_ip = config.get("client_ip")
        if client_ip is not None:
            if not isinstance(client_ip, str):
                raise InvalidWebRTCConfig("client_ip must be a string.")
            try:
                ip_address(client_ip)
            except ValueError:
                raise InvalidWebRTCConfig(
                    "client_ip must be a valid IPv4 or IPv6 address."
                ) from None
    return validated


def _normalize_metered_app_name(value: object) -> str:
    if isinstance(value, str):
        app_name = value.strip().lower()
        if app_name.endswith(_METERED_DOMAIN_SUFFIX):
            app_name = app_name[: -len(_METERED_DOMAIN_SUFFIX)]
        if _METERED_APP_NAME_PATTERN.fullmatch(app_name):
            return app_name

    raise InvalidWebRTCConfig(
        "Metered domain must be the value shown in the Metered dashboard "
        "(for example, your_app.metered.live) or its app name."
    )


def _validate_secrets(
    secrets: Mapping[str, str],
    provider: WebRTCProviders,
) -> Mapping[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidWebRTCConfig("Secrets must be a mapping.")
    unknown = set(secrets) - {_SECRET_FIELD_NAME}
    if unknown:
        raise InvalidWebRTCConfig(
            f"Unknown secret fields for {provider.value}: {sorted(unknown)}"
        )
    api_key = secrets.get(_SECRET_FIELD_NAME)
    if not isinstance(api_key, str) or not api_key.strip():
        raise InvalidWebRTCConfig(
            f"Provider {provider.value} requires a non-empty api_key secret."
        )
    return dict(secrets)


def _is_configured_value(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_number(
    config: Mapping[str, object],
    field_name: str,
    *,
    minimum: float,
    maximum: float,
    inclusive_minimum: bool = True,
) -> None:
    value = config.get(field_name)
    if value is None:
        return
    is_number = not isinstance(value, bool) and isinstance(value, (int, float))
    lower_bound_valid = is_number and (
        value >= minimum if inclusive_minimum else value > minimum
    )
    if not lower_bound_valid or value > maximum:
        comparator = ">=" if inclusive_minimum else ">"
        raise InvalidWebRTCConfig(
            f"{field_name} must be a number {comparator} {minimum} and <= {maximum}."
        )


def _validate_integer(
    config: Mapping[str, object],
    field_name: str,
    *,
    minimum: int,
    maximum: int,
) -> None:
    value = config.get(field_name)
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise InvalidWebRTCConfig(
            f"{field_name} must be an integer between {minimum} and {maximum}."
        )


def _validate_optional_string(
    config: Mapping[str, object],
    field_name: str,
) -> None:
    value = config.get(field_name)
    if value is not None and not _is_configured_value(value):
        raise InvalidWebRTCConfig(f"{field_name} must be a non-empty string.")


@dataclass(frozen=True)
class ResolvedWebRTC:
    """Immutable resolved WebRTC runtime value with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: WebRTCProviders
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
    ) -> ResolvedWebRTC:
        validated = WebRTCProviderConfig.validate(
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

    @property
    def secret(self) -> str:
        return self.secrets[_SECRET_FIELD_NAME]
