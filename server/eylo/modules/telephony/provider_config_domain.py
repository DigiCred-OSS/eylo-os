"""Strict telephony provider configuration and resolved runtime authority."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address
from types import MappingProxyType
from urllib.parse import urlparse
from uuid import UUID

from cryptography.hazmat.primitives import serialization

from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)

__all__ = [
    "InvalidTelephonyConfig",
    "ResolvedTelephony",
    "TelephonyOperation",
    "TelephonyProvider",
    "TelephonyProviderConfig",
    "supports_telephony_operation",
    "telephony_operation_matrix",
]


class TelephonyProvider(str, Enum):
    TWILIO = "twilio"
    PLIVO = "plivo"
    VONAGE = "vonage"
    EXOTEL = "exotel"


class TelephonyOperation(str, Enum):
    """Carrier operations exposed by the common telephony contract."""

    SEARCH_NUMBERS = "search_numbers"
    PURCHASE_NUMBER = "purchase_number"
    RELEASE_NUMBER = "release_number"
    INBOUND_CALL = "inbound_call"
    OUTBOUND_CALL = "outbound_call"
    BIDIRECTIONAL_MEDIA = "bidirectional_media"
    END_CALL = "end_call"
    TRANSFER_CALL = "transfer_call"
    RECEIVE_DTMF = "receive_dtmf"
    SEND_DTMF = "send_dtmf"
    AUTHENTICATED_STATUS_CALLBACK = "authenticated_status_callback"


_IMPLEMENTED_TELEPHONY_OPERATIONS = frozenset(TelephonyOperation) - {
    TelephonyOperation.RELEASE_NUMBER,
}
_EXOTEL_OPERATIONS = _IMPLEMENTED_TELEPHONY_OPERATIONS - {
    TelephonyOperation.TRANSFER_CALL,
    TelephonyOperation.AUTHENTICATED_STATUS_CALLBACK,
}
_PLIVO_OPERATIONS = _IMPLEMENTED_TELEPHONY_OPERATIONS - {
    TelephonyOperation.TRANSFER_CALL,
}
_OPERATIONS_BY_PROVIDER = MappingProxyType(
    {
        TelephonyProvider.TWILIO: _IMPLEMENTED_TELEPHONY_OPERATIONS,
        TelephonyProvider.PLIVO: _PLIVO_OPERATIONS,
        TelephonyProvider.VONAGE: _IMPLEMENTED_TELEPHONY_OPERATIONS,
        TelephonyProvider.EXOTEL: _EXOTEL_OPERATIONS,
    }
)


def supports_telephony_operation(
    provider: TelephonyProvider | str,
    operation: TelephonyOperation,
) -> bool:
    """Return whether one carrier implements an operation in this release."""
    return operation in _OPERATIONS_BY_PROVIDER[_provider(provider)]


def telephony_operation_matrix(
    provider: TelephonyProvider | str,
) -> dict[TelephonyOperation, bool]:
    """Return every common operation, including explicit unsupported entries."""
    supported = _OPERATIONS_BY_PROVIDER[_provider(provider)]
    return {operation: operation in supported for operation in TelephonyOperation}


class InvalidTelephonyConfig(InvalidProviderConfig):
    """Raised when a telephony provider config violates its contract."""


_CONFIG_FIELDS = {
    TelephonyProvider.TWILIO: frozenset({"webhook_base_url"}),
    TelephonyProvider.PLIVO: frozenset({"webhook_base_url"}),
    TelephonyProvider.VONAGE: frozenset({"webhook_base_url", "application_id"}),
    TelephonyProvider.EXOTEL: frozenset(
        {"webhook_base_url", "application_id", "api_host"}
    ),
}
_SECRET_FIELDS = {
    TelephonyProvider.TWILIO: frozenset({"account_sid", "auth_token"}),
    TelephonyProvider.PLIVO: frozenset({"auth_id", "auth_token"}),
    TelephonyProvider.VONAGE: frozenset(
        {"api_key", "api_secret", "private_key", "signature_secret"}
    ),
    TelephonyProvider.EXOTEL: frozenset({"api_key", "api_token", "account_sid"}),
}
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])$"
)


@dataclass(frozen=True)
class TelephonyProviderConfig:
    """Validated provider settings with plaintext secrets held in memory only."""

    provider: TelephonyProvider | str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        provider = _provider(self.provider)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "config",
            MappingProxyType(_validate_config(self.config, provider)),
        )
        object.__setattr__(
            self,
            "secrets",
            MappingProxyType(_validate_secrets(self.secrets, provider)),
        )

    @classmethod
    def validate(
        cls,
        *,
        provider: TelephonyProvider | str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> TelephonyProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    def secret(self, name: str) -> str:
        return self.secrets[name]

    def adapter_settings(self) -> dict[str, object]:
        """Translate canonical provider fields to the current socket contract."""
        settings = {**self.config, **self.secrets}
        if self.provider is TelephonyProvider.EXOTEL:
            settings["exotel_app_id"] = self.config["application_id"]
            settings["subdomain"] = self.config["api_host"]
        return settings


@dataclass(frozen=True)
class ResolvedTelephony:
    """Immutable, explicit carrier-account authority for runtime work."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: TelephonyProvider
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
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
    ) -> ResolvedTelephony:
        validated = TelephonyProviderConfig.validate(
            provider=provider_config.provider,
            config=provider_config.settings,
            secrets=provider_config.secrets,
        )
        return cls(
            provider_config_id=provider_config.provider_config_id,
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

    def as_provider_config(self) -> TelephonyProviderConfig:
        return TelephonyProviderConfig.validate(
            provider=self.provider,
            config=self.config,
            secrets=self.secrets,
        )


def _provider(value: TelephonyProvider | str) -> TelephonyProvider:
    if isinstance(value, TelephonyProvider):
        return value
    try:
        return TelephonyProvider(str(value).strip().lower())
    except ValueError:
        raise InvalidTelephonyConfig(
            f"Unsupported telephony provider: {value}"
        ) from None


def _validate_config(
    config: Mapping[str, object],
    provider: TelephonyProvider,
) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidTelephonyConfig("Config must be a mapping.")
    expected = _CONFIG_FIELDS[provider]
    _require_exact_fields(config, expected, provider, "config")

    normalized = dict(config)
    normalized["webhook_base_url"] = _validate_https_url(
        config["webhook_base_url"],
        "webhook_base_url",
    )
    if provider in {TelephonyProvider.VONAGE, TelephonyProvider.EXOTEL}:
        normalized["application_id"] = _validate_string(
            config["application_id"],
            "application_id",
            maximum=255,
        )
    if provider is TelephonyProvider.EXOTEL:
        normalized["api_host"] = _validate_exotel_host(config["api_host"])
    return normalized


def _validate_secrets(
    secrets: Mapping[str, str],
    provider: TelephonyProvider,
) -> dict[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidTelephonyConfig("Secrets must be a mapping.")
    expected = _SECRET_FIELDS[provider]
    _require_exact_fields(secrets, expected, provider, "secrets")
    normalized = {
        name: _validate_string(value, name, maximum=16_384)
        for name, value in secrets.items()
    }
    if provider is TelephonyProvider.VONAGE:
        _validate_private_key(normalized["private_key"])
    return normalized


def _require_exact_fields(
    values: Mapping[str, object],
    expected: frozenset[str],
    provider: TelephonyProvider,
    kind: str,
) -> None:
    unknown = sorted(set(values) - expected)
    missing = sorted(expected - set(values))
    if unknown:
        raise InvalidTelephonyConfig(
            f"Unknown {kind} fields for {provider.value}: {unknown}"
        )
    if missing:
        raise InvalidTelephonyConfig(
            f"Provider {provider.value} requires {kind} fields: {missing}"
        )


def _validate_string(value: object, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InvalidTelephonyConfig(
            f"{field_name} must be a non-empty string of at most {maximum} characters."
        )
    return value.strip()


def _validate_https_url(value: object, field_name: str) -> str:
    text = _validate_string(value, field_name, maximum=2_048).rstrip("/")
    parsed = urlparse(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidTelephonyConfig(
            f"{field_name} must be an HTTPS origin or path without credentials, query, or fragment."
        )
    _require_public_host(parsed.hostname, field_name)
    return text


def _validate_exotel_host(value: object) -> str:
    host = _validate_string(value, "api_host", maximum=253).lower().rstrip(".")
    _require_public_host(host, "api_host")
    if host != "api.exotel.com" and not host.endswith(".exotel.com"):
        raise InvalidTelephonyConfig("api_host must be an Exotel API host.")
    return host


def _require_public_host(host: str, field_name: str) -> None:
    try:
        address = ip_address(host)
    except ValueError:
        if not _HOST_PATTERN.fullmatch(host.lower()):
            raise InvalidTelephonyConfig(
                f"{field_name} must contain a valid public host."
            ) from None
    else:
        if not address.is_global:
            raise InvalidTelephonyConfig(f"{field_name} must contain a public host.")


def _validate_private_key(value: str) -> None:
    try:
        serialization.load_pem_private_key(value.encode(), password=None)
    except (TypeError, ValueError):
        raise InvalidTelephonyConfig(
            "private_key must be an unencrypted PEM private key."
        ) from None
