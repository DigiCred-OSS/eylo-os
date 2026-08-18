"""Voice config service — validation, CRUD orchestration, and resolution."""

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
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.domain import VoiceProviderConfig

__all__ = ["VoiceConfigService"]


class VoiceConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


class VoiceConfigService:
    """Validates and persists STT/TTS provider configs on the shared foundation."""

    def __init__(
        self,
        provider_configs: ProviderConfigService,
        references: VoiceConfigReferences | None = None,
    ) -> None:
        self._provider_configs = provider_configs
        self._references = references

    async def create(
        self,
        *,
        organization_id: UUID,
        kind: VoiceKind,
        provider: str,
        name: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> ProviderConfig:
        validated = VoiceProviderConfig.validate(
            provider=provider,
            kind=kind,
            config=config,
            secrets=secrets,
        )
        capability = Capability(kind.value)
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=capability,
            provider=validated.provider.value,
            name=name,
            config=validated.config,
            secrets=validated.secrets,
        )

    async def list(
        self,
        *,
        organization_id: UUID,
        kind: VoiceKind,
    ) -> list[ProviderConfig]:
        capability = Capability(kind.value)
        configs = await self._provider_configs.list(
            organization_id=organization_id,
            capability=capability,
        )
        for config in configs:
            if not config.credentials_available:
                continue
            VoiceProviderConfig.validate(
                provider=config.provider,
                kind=kind,
                config=config.config,
                secrets=config.secrets,
            )
        return configs

    async def get(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        kind: VoiceKind,
    ) -> ProviderConfig:
        config = await self._provider_configs.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        expected_capability = Capability(kind.value)
        if config.capability is not expected_capability:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        VoiceProviderConfig.validate(
            provider=config.provider,
            kind=kind,
            config=config.config,
            secrets=config.secrets,
        )
        return config

    async def update(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        kind: VoiceKind,
        name: str | None = None,
        config: Mapping[str, object] | None = None,
        secret_patch: Mapping[str, str | None] | None = None,
        enabled: bool | None = None,
    ) -> ProviderConfig:
        existing = await self.get(
            organization_id=organization_id,
            config_id=config_id,
            kind=kind,
        )
        merged_config = existing.config if config is None else config
        merged_secrets = (
            existing.secrets
            if secret_patch is None
            else apply_secret_patch(existing.secrets, secret_patch)
        )
        VoiceProviderConfig.validate(
            provider=existing.provider,
            kind=kind,
            config=merged_config,
            secrets=merged_secrets,
        )
        updated = existing
        if name is not None or config is not None or secret_patch is not None:
            updated = await self._provider_configs.update(
                organization_id=organization_id,
                config_id=config_id,
                name=name,
                config=config,
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
        kind: VoiceKind,
        granted: bool,
    ) -> EffectiveProviderConfig:
        return await self._provider_configs.resolve_for_new_run(
            organization_id=organization_id,
            capability=Capability(kind.value),
            config_id=config_id,
            granted=granted,
            configure_via=f"/api/{kind.value}-configs",
        )

    async def resolve_pinned(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        revision: int,
        kind: VoiceKind,
        granted: bool,
    ) -> EffectiveProviderConfig:
        return await self._provider_configs.resolve_pinned(
            organization_id=organization_id,
            capability=Capability(kind.value),
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via=f"/api/{kind.value}-configs",
        )

    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        kind: VoiceKind,
    ) -> None:
        await self.get(
            organization_id=organization_id,
            config_id=config_id,
            kind=kind,
        )
        if self._references is None:
            raise ProviderConfigConflict(
                "Voice config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "Voice config is referenced by an agent voice definition."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )
