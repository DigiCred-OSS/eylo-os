"""Application services for the `llm_configs` domain."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from eylo.modules.llm_configs.domain import LLMProviderConfig
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    ProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.provider_configs.service import ProviderConfigService


class LLMConfigService:
    """Organization-scoped LLM config lifecycle over shared persistence."""

    def __init__(
        self,
        provider_configs: ProviderConfigService,
        *,
        references: LLMConfigReferences | None = None,
    ):
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
        validated = LLMProviderConfig.validate(
            provider=provider,
            config=config,
            secrets=secrets,
        )
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=Capability.LLM,
            provider=validated.storage_provider,
            name=name,
            config=validated.config_for_storage(),
            secrets=validated.secrets,
        )

    async def list(self, *, organization_id: UUID) -> list[ProviderConfig]:
        configs = await self._provider_configs.list(
            organization_id=organization_id,
            capability=Capability.LLM,
        )
        for config in configs:
            if not config.credentials_available:
                continue
            to_llm_provider_config(config)
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
        to_llm_provider_config(config)
        return config

    async def update(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        name: str | None = None,
        config_patch: Mapping[str, object] | None = None,
        secret_patch: Mapping[str, str | None] | None = None,
        enabled: bool | None = None,
    ) -> ProviderConfig:
        current = await self.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        effective_config = dict(current.config)
        if config_patch is not None:
            effective_config.update(config_patch)
        effective_secrets = (
            current.secrets
            if secret_patch is None
            else apply_secret_patch(current.secrets, secret_patch)
        )
        validated = LLMProviderConfig.validate(
            provider=current.provider,
            config=effective_config,
            secrets=effective_secrets,
        )
        updated = current
        if name is not None or config_patch is not None or secret_patch is not None:
            updated = await self._provider_configs.update(
                organization_id=organization_id,
                config_id=config_id,
                name=name,
                config=(
                    validated.config_for_storage()
                    if config_patch is not None
                    else None
                ),
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
            capability=Capability.LLM,
            config_id=config_id,
            granted=granted,
            configure_via="/api/llm-configs",
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
            capability=Capability.LLM,
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via="/api/llm-configs",
        )

    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        config = await self._provider_configs.get_for_update(
            organization_id=organization_id,
            config_id=config_id,
        )
        if config.capability is not Capability.LLM:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        if self._references is None:
            raise ProviderConfigConflict(
                "LLM config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "LLM config is referenced by an agent or Memory configuration."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )


class LLMConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


def to_llm_provider_config(config: ProviderConfig) -> LLMProviderConfig:
    """Validate and translate a shared aggregate into the LLM domain."""
    if config.capability is not Capability.LLM:
        raise ProviderConfigNotFound("LLM provider config was not found.")
    return LLMProviderConfig.validate(
        provider=config.provider,
        config=config.config,
        secrets=config.secrets,
    )


def effective_to_llm_provider_config(
    config: EffectiveProviderConfig,
) -> LLMProviderConfig:
    if config.capability is not Capability.LLM:
        raise ProviderConfigNotFound("LLM provider config was not found.")
    return LLMProviderConfig.validate(
        provider=config.provider,
        config=config.settings,
        secrets=config.secrets,
    )
