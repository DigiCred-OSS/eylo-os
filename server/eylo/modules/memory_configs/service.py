"""Organization-owned memory config lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from eylo.modules.memory_configs.domain import MemoryProviderConfig
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    ProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.provider_configs.service import ProviderConfigService

__all__ = ["MemoryConfigReferences", "MemoryConfigService"]


class MemoryConfigService:
    def __init__(
        self,
        provider_configs: ProviderConfigService,
        *,
        references: MemoryConfigReferences | None = None,
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
        validated = MemoryProviderConfig.validate(
            provider=provider,
            config=config,
            secrets=secrets,
        )
        await self._require_ready_dependencies(
            organization_id=organization_id,
            config=validated,
        )
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=Capability.MEMORY,
            provider=validated.provider.value,
            name=name,
            config=validated.config,
            secrets=validated.secrets,
        )

    async def list(self, *, organization_id: UUID) -> list[ProviderConfig]:
        return await self._provider_configs.list(
            organization_id=organization_id,
            capability=Capability.MEMORY,
        )

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
        if config.capability is not Capability.MEMORY:
            raise ProviderConfigNotFound("Provider configuration was not found.")
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
        validated = MemoryProviderConfig.validate(
            provider=existing.provider,
            config=next_config,
            secrets=next_secrets,
        )
        if config is not None or enabled is True:
            await self._require_ready_dependencies(
                organization_id=organization_id,
                config=validated,
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

    async def _require_ready_dependencies(
        self,
        *,
        organization_id: UUID,
        config: MemoryProviderConfig,
    ) -> None:
        await self._require_ready_dependency(
            organization_id=organization_id,
            config_id=config.embedding_provider_config_id,
            capability=Capability.EMBEDDING,
        )
        await self._require_ready_dependency(
            organization_id=organization_id,
            config_id=config.llm_provider_config_id,
            capability=Capability.LLM,
        )

    async def _require_ready_dependency(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        capability: Capability,
    ) -> None:
        dependency = await self._provider_configs.get_for_update(
            organization_id=organization_id,
            config_id=config_id,
        )
        if dependency.capability is not capability:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        if not dependency.ready:
            raise ProviderConfigConflict(
                f"{capability.value.capitalize()} provider configuration must be ready."
            )

    async def mark_verified(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        expected_revision: int,
        verification_metadata: Mapping[str, object],
    ) -> ProviderConfig:
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
            capability=Capability.MEMORY,
            config_id=config_id,
            granted=granted,
            configure_via="/api/memory-configs",
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
            capability=Capability.MEMORY,
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via="/api/memory-configs",
        )

    async def delete(self, *, organization_id: UUID, config_id: UUID) -> None:
        await self.get(organization_id=organization_id, config_id=config_id)
        if self._references is None:
            raise ProviderConfigConflict(
                "Memory config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "Memory config is referenced by an agent, fact, or durable job."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )


class MemoryConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...
