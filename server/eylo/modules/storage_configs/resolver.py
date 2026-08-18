"""Resolve one explicit organization storage config or pinned revision."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.storage_configs.domain import InvalidStorageConfig, ResolvedStorage
from eylo.modules.storage_configs.service import StorageConfigService

__all__ = ["StorageConfigResolver"]


class StorageConfigResolver:
    def __init__(self, configs: StorageConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedStorage:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        effective = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        return _to_resolved(effective, organization_id)

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedStorage:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return _to_resolved(effective, organization_id)


def _to_resolved(effective, organization_id: UUID) -> ResolvedStorage:
    try:
        return ResolvedStorage.from_provider_config(
            provider_config_id=effective.provider_config_id,
            organization_id=organization_id,
            provider_config=effective,
        )
    except InvalidStorageConfig:
        raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.STORAGE,
        missing=[missing],
        configure_via="/api/storage-configs",
    )
