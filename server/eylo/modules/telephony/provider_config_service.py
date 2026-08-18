"""Telephony config lifecycle and explicit revision resolution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    ProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.telephony.provider_config_domain import (
    InvalidTelephonyConfig,
    ResolvedTelephony,
    TelephonyProviderConfig,
)

__all__ = [
    "TelephonyConfigReferences",
    "TelephonyConfigResolver",
    "TelephonyConfigService",
]

_CONFIGURE_VIA = "/api/telephony-configs"


class TelephonyConfigService:
    """Organization-scoped lifecycle over the shared provider-config plane."""

    def __init__(
        self,
        provider_configs: ProviderConfigService,
        *,
        references: TelephonyConfigReferences | None = None,
    ) -> None:
        self._provider_configs = provider_configs
        self._references = references

    async def create(
        self,
        *,
        organization_id: UUID,
        provider: str,
        name: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> ProviderConfig:
        validated = TelephonyProviderConfig.validate(
            provider=provider,
            config=config,
            secrets=secrets,
        )
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=Capability.TELEPHONY,
            provider=validated.provider.value,
            name=name,
            config=validated.config,
            secrets=validated.secrets,
        )

    async def list(self, *, organization_id: UUID) -> list[ProviderConfig]:
        configs = await self._provider_configs.list(
            organization_id=organization_id,
            capability=Capability.TELEPHONY,
        )
        for config in configs:
            if not config.credentials_available:
                continue
            _validate_stored(config)
        return configs

    async def get(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig:
        config = await self._provider_configs.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        if config.capability is not Capability.TELEPHONY:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        _validate_stored(config)
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
        next_config = existing.config if config is None else config
        next_secrets = (
            existing.secrets
            if secret_patch is None
            else apply_secret_patch(existing.secrets, secret_patch)
        )
        validated = TelephonyProviderConfig.validate(
            provider=existing.provider,
            config=next_config,
            secrets=next_secrets,
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
        verification_metadata: Mapping[str, object] | None = None,
    ) -> ProviderConfig:
        await self.get(organization_id=organization_id, config_id=config_id)
        return await self._provider_configs.mark_verified(
            organization_id=organization_id,
            config_id=config_id,
            expected_revision=expected_revision,
            verification_metadata=verification_metadata,
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
            capability=Capability.TELEPHONY,
            config_id=config_id,
            granted=granted,
            configure_via=_CONFIGURE_VIA,
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
            capability=Capability.TELEPHONY,
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via=_CONFIGURE_VIA,
        )

    async def delete(self, *, organization_id: UUID, config_id: UUID) -> None:
        await self.get(organization_id=organization_id, config_id=config_id)
        if self._references is None:
            raise ProviderConfigConflict(
                "Telephony config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "Telephony config is referenced by a phone number or call."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )


class TelephonyConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


class TelephonyConfigResolver:
    """Resolve only an explicit current or pinned carrier-account revision."""

    def __init__(self, configs: TelephonyConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedTelephony:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        effective = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        return _resolved(organization_id, effective)

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedTelephony:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return _resolved(organization_id, effective)


def _validate_stored(config: ProviderConfig) -> None:
    TelephonyProviderConfig.validate(
        provider=config.provider,
        config=config.config,
        secrets=config.secrets,
    )


def _resolved(
    organization_id: UUID,
    effective: EffectiveProviderConfig,
) -> ResolvedTelephony:
    try:
        return ResolvedTelephony.from_provider_config(
            organization_id=organization_id,
            provider_config=effective,
        )
    except InvalidTelephonyConfig:
        raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.TELEPHONY,
        missing=[missing],
        configure_via=_CONFIGURE_VIA,
    )
