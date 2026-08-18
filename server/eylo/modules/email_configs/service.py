"""Email config lifecycle on the shared provider-config foundation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from eylo.modules.email_configs.catalog import EmailProviders
from eylo.modules.email_configs.domain import EmailProviderConfig, InvalidEmailConfig
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    ProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.provider_configs.service import ProviderConfigService

__all__ = ["EmailConfigService"]

_SMTP_AUTHORITY_FIELDS = frozenset(
    {"smtp_host", "smtp_port", "smtp_username", "smtp_security"}
)


class EmailConfigService:
    def __init__(
        self,
        provider_configs: ProviderConfigService,
        *,
        references: EmailConfigReferences | None = None,
    ) -> None:
        self._provider_configs = provider_configs
        self._references = references

    async def create(
        self,
        *,
        organization_id: UUID,
        provider: str,
        name: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> ProviderConfig:
        validated = EmailProviderConfig.validate(
            provider=provider,
            config=config,
            secrets=secrets,
        )
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=Capability.EMAIL,
            provider=validated.provider.value,
            name=name,
            config=validated.config,
            secrets=validated.secrets,
        )

    async def list(self, *, organization_id: UUID) -> list[ProviderConfig]:
        configs = await self._provider_configs.list(
            organization_id=organization_id,
            capability=Capability.EMAIL,
        )
        for config in configs:
            if not config.credentials_available:
                continue
            EmailProviderConfig.validate(
                provider=config.provider,
                config=config.config,
                secrets=config.secrets,
            )
        return configs

    async def get(self, *, organization_id: UUID, config_id: UUID) -> ProviderConfig:
        config = await self._provider_configs.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        if config.capability is not Capability.EMAIL:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        EmailProviderConfig.validate(
            provider=config.provider,
            config=config.config,
            secrets=config.secrets,
        )
        return config

    async def update(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        name: str | None = None,
        config: Mapping[str, object] | None = None,
        secret_patch: Mapping[str, str | None] | None = None,
        enabled: bool | None = None,
    ) -> ProviderConfig:
        existing = await self.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        merged_config = existing.config if config is None else config
        merged_secrets = (
            existing.secrets
            if secret_patch is None
            else apply_secret_patch(existing.secrets, secret_patch)
        )
        _require_smtp_secret_replacement(
            existing=existing,
            next_config=merged_config,
            secret_patch=secret_patch,
        )
        validated = EmailProviderConfig.validate(
            provider=existing.provider,
            config=merged_config,
            secrets=merged_secrets,
        )
        updated = existing
        if name is not None or config is not None or secret_patch is not None:
            updated = await self._provider_configs.update(
                organization_id=organization_id,
                config_id=config_id,
                name=name,
                config=validated.config if config is not None else None,
                secret_patch=secret_patch,
            )
        if enabled is not None:
            updated = await self._provider_configs.set_enabled(
                organization_id=organization_id,
                config_id=config_id,
                enabled=enabled,
            )
        return updated

    async def mark_verified(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        expected_revision: int,
    ) -> ProviderConfig:
        return await self._provider_configs.mark_verified(
            organization_id=organization_id,
            config_id=config_id,
            expected_revision=expected_revision,
        )

    async def resolve_for_new_run(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        granted: bool,
    ) -> EffectiveProviderConfig:
        return await self._provider_configs.resolve_for_new_run(
            organization_id=organization_id,
            capability=Capability.EMAIL,
            config_id=config_id,
            granted=granted,
            configure_via="/api/email-configs",
        )

    async def resolve_pinned(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        revision: int,
        granted: bool,
    ) -> EffectiveProviderConfig:
        return await self._provider_configs.resolve_pinned(
            organization_id=organization_id,
            capability=Capability.EMAIL,
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via="/api/email-configs",
        )

    async def delete(self, *, organization_id: UUID, config_id: UUID) -> None:
        await self.get(organization_id=organization_id, config_id=config_id)
        if self._references is None:
            raise ProviderConfigConflict(
                "Email config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "Email config is referenced by an agent definition."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )


class EmailConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


def _require_smtp_secret_replacement(
    *,
    existing: ProviderConfig,
    next_config: Mapping[str, object],
    secret_patch: Mapping[str, str | None] | None,
) -> None:
    if existing.provider != EmailProviders.SMTP.value:
        return
    authority_changed = any(
        existing.config.get(field_name) != next_config.get(field_name)
        for field_name in _SMTP_AUTHORITY_FIELDS
    )
    if authority_changed and (
        secret_patch is None or not secret_patch.get("smtp_password")
    ):
        raise InvalidEmailConfig(
            "SMTP endpoint, security, or username changes require smtp_password replacement."
        )
