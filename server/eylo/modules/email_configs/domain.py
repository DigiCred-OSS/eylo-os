"""Provider-specific validation and resolved runtime values for email configs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
from uuid import UUID

from pydantic import EmailStr, TypeAdapter, ValidationError

from eylo.modules.email_configs.catalog import EmailProviders
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)

__all__ = ["InvalidEmailConfig", "ResolvedEmail", "EmailProviderConfig"]

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$"
)
_COMMON_CONFIG_FIELDS = frozenset(
    {"default_from_email", "default_from_name", "timeout"}
)
_CONFIG_FIELDS = {
    EmailProviders.SENDGRID: _COMMON_CONFIG_FIELDS,
    EmailProviders.SMTP: _COMMON_CONFIG_FIELDS
    | {"smtp_host", "smtp_port", "smtp_username", "smtp_security"},
}
_REQUIRED_CONFIG_FIELDS = _CONFIG_FIELDS
_SECRET_FIELDS = {
    EmailProviders.SENDGRID: frozenset({"api_key"}),
    EmailProviders.SMTP: frozenset({"smtp_password"}),
}


class InvalidEmailConfig(InvalidProviderConfig):
    """Raised when an email provider config violates policy."""


@dataclass(frozen=True)
class EmailProviderConfig:
    """Validated email config with plaintext secrets held in memory only."""

    provider: str
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        provider_value = str(self.provider).lower().strip()
        try:
            provider = EmailProviders(provider_value)
        except ValueError:
            raise InvalidEmailConfig(
                f"Unknown email provider: {self.provider}"
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
    ) -> EmailProviderConfig:
        return cls(
            provider=provider,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    def secret(self, name: str) -> str:
        return self.secrets[name]


def _validate_config(
    config: Mapping[str, object],
    provider: EmailProviders,
) -> Mapping[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidEmailConfig("Config must be a mapping.")
    unknown = set(config) - _CONFIG_FIELDS[provider]
    if unknown:
        raise InvalidEmailConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field_name
        for field_name in _REQUIRED_CONFIG_FIELDS[provider]
        if config.get(field_name) is None
    ]
    if missing:
        raise InvalidEmailConfig(
            f"Provider {provider.value} requires config fields: {missing}"
        )

    normalized = dict(config)
    normalized["default_from_email"] = _validate_email(
        config["default_from_email"],
        "default_from_email",
    )
    normalized["default_from_name"] = _validate_string(
        config["default_from_name"],
        "default_from_name",
        maximum=255,
    )
    normalized["timeout"] = _validate_timeout(config["timeout"])

    if provider is EmailProviders.SMTP:
        normalized["smtp_host"] = _validate_smtp_host(config["smtp_host"])
        normalized["smtp_port"] = _validate_smtp_port(config["smtp_port"])
        normalized["smtp_username"] = _validate_string(
            config["smtp_username"],
            "smtp_username",
            maximum=320,
        )
        security = config["smtp_security"]
        if security not in {"implicit_tls", "starttls"}:
            raise InvalidEmailConfig(
                "smtp_security must be implicit_tls or starttls."
            )
    return normalized


def _validate_secrets(
    secrets: Mapping[str, str],
    provider: EmailProviders,
) -> Mapping[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidEmailConfig("Secrets must be a mapping.")
    expected = _SECRET_FIELDS[provider]
    unknown = set(secrets) - expected
    if unknown:
        raise InvalidEmailConfig(
            f"Unknown secret fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field_name
        for field_name in expected
        if not isinstance(secrets.get(field_name), str)
        or not secrets[field_name].strip()
    ]
    if missing:
        raise InvalidEmailConfig(
            f"Provider {provider.value} requires non-empty secrets: {missing}"
        )
    return dict(secrets)


def _validate_email(value: object, field_name: str) -> str:
    try:
        return str(_EMAIL_ADAPTER.validate_python(value))
    except ValidationError:
        raise InvalidEmailConfig(f"{field_name} must be a valid email.") from None


def _validate_string(value: object, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InvalidEmailConfig(
            f"{field_name} must be a non-empty string of at most {maximum} characters."
        )
    return value.strip()


def _validate_timeout(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or value > 60
    ):
        raise InvalidEmailConfig("timeout must be a number greater than 0 and <= 60.")
    return float(value)


def _validate_smtp_port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise InvalidEmailConfig("smtp_port must be an integer between 1 and 65535.")
    return value


def _validate_smtp_host(value: object) -> str:
    host = _validate_string(value, "smtp_host", maximum=253).lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"}:
        raise InvalidEmailConfig("smtp_host must be a public host.")
    try:
        address = ip_address(host)
    except ValueError:
        if "." not in host or not _HOST_PATTERN.fullmatch(host):
            raise InvalidEmailConfig("smtp_host must be a valid public host.") from None
    else:
        if not address.is_global:
            raise InvalidEmailConfig("smtp_host must be a public host.")
    return host


@dataclass(frozen=True)
class ResolvedEmail:
    """Immutable resolved email runtime value with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: EmailProviders
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
    ) -> ResolvedEmail:
        validated = EmailProviderConfig.validate(
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
