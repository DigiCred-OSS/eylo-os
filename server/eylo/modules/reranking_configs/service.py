"""Organization-owned reranking config lifecycle."""

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
from eylo.modules.reranking_configs.domain import (
    InvalidRerankingConfig,
    RerankingEndpointPolicy,
    RerankingProviderConfig,
)

__all__ = ["RerankingConfigReferences", "RerankingConfigService"]


class RerankingConfigService:
    def __init__(
        self,
        provider_configs: ProviderConfigService,
        *,
        endpoint_policy: RerankingEndpointPolicy | None = None,
        references: RerankingConfigReferences | None = None,
    ) -> None:
        self._provider_configs = provider_configs
        self.endpoint_policy = endpoint_policy or RerankingEndpointPolicy()
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
        validated = self._validate(provider, config, secrets)
        return await self._provider_configs.create(
            organization_id=organization_id,
            capability=Capability.RERANKING,
            provider=validated.provider.value,
            name=name,
            config=validated.config,
            secrets=validated.secrets,
        )

    async def list(self, *, organization_id: UUID) -> list[ProviderConfig]:
        return await self._provider_configs.list(
            organization_id=organization_id,
            capability=Capability.RERANKING,
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
        if config.capability is not Capability.RERANKING:
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
        _require_endpoint_secret_replacement(
            existing=existing,
            next_config=next_config,
            secret_patch=secret_patch,
        )
        validated = self._validate(existing.provider, next_config, next_secrets)
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
            capability=Capability.RERANKING,
            config_id=config_id,
            granted=granted,
            configure_via="/api/reranking-configs",
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
            capability=Capability.RERANKING,
            config_id=config_id,
            revision=revision,
            granted=granted,
            configure_via="/api/reranking-configs",
        )

    async def delete(self, *, organization_id: UUID, config_id: UUID) -> None:
        await self.get(organization_id=organization_id, config_id=config_id)
        if self._references is None:
            raise ProviderConfigConflict(
                "Reranking config deletion requires a reference check."
            )
        if await self._references.has_references(
            organization_id=organization_id,
            config_id=config_id,
        ):
            raise ProviderConfigConflict(
                "Reranking config is referenced by an agent definition."
            )
        await self._provider_configs.delete(
            organization_id=organization_id,
            config_id=config_id,
        )

    def _validate(
        self,
        provider: str,
        config: Mapping[str, object] | None,
        secrets: Mapping[str, str] | None,
    ) -> RerankingProviderConfig:
        return RerankingProviderConfig.validate(
            provider=provider,
            config=config,
            secrets=secrets,
            endpoint_policy=self.endpoint_policy,
        )


class RerankingConfigReferences(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


def _require_endpoint_secret_replacement(
    *,
    existing: ProviderConfig,
    next_config: Mapping[str, object],
    secret_patch: Mapping[str, str | None] | None,
) -> None:
    if existing.config.get("base_url") == next_config.get("base_url"):
        return
    if secret_patch is None or not secret_patch.get("api_key"):
        raise InvalidRerankingConfig(
            "Changing base_url requires complete api_key replacement."
        )
