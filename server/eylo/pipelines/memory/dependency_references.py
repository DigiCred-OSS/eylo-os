"""Memory-config references that block dependency deletion."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.memory_configs.domain import (
    EMBEDDING_PROVIDER_CONFIG_ID_KEY,
    LLM_PROVIDER_CONFIG_ID_KEY,
)
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.models import (
    ProviderConfigModel,
    ProviderConfigRevisionModel,
)

_DEPENDENCY_KEY = {
    Capability.EMBEDDING: EMBEDDING_PROVIDER_CONFIG_ID_KEY,
    Capability.LLM: LLM_PROVIDER_CONFIG_ID_KEY,
}


class MemoryDependencyReferenceLookup:
    """Find current or pinned Memory revisions using one provider config."""

    def __init__(self, db: AsyncSession, capability: Capability) -> None:
        try:
            self._config_key = _DEPENDENCY_KEY[capability]
        except KeyError:
            raise ValueError(
                "Memory dependencies support only LLM and embedding configs."
            ) from None
        self._db = db

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        dependency = {self._config_key: str(config_id)}
        current = await self._db.scalar(
            select(
                exists().where(
                    ProviderConfigModel.organization_id == organization_id,
                    ProviderConfigModel.capability == Capability.MEMORY,
                    ProviderConfigModel.config.contains(dependency),
                    ProviderConfigModel.deleted.is_(False),
                )
            )
        )
        if current:
            return True

        historical = await self._db.scalar(
            select(
                exists().where(
                    ProviderConfigRevisionModel.organization_id == organization_id,
                    ProviderConfigRevisionModel.config.contains(dependency),
                    ProviderConfigModel.id
                    == ProviderConfigRevisionModel.provider_config_id,
                    ProviderConfigModel.organization_id == organization_id,
                    ProviderConfigModel.capability == Capability.MEMORY,
                    ProviderConfigModel.deleted.is_(False),
                )
            )
        )
        return bool(historical)


class ProviderConfigReferenceLookup(Protocol):
    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool: ...


class CombinedProviderConfigReferences:
    """Answer true when any composed product reference owns the config."""

    def __init__(self, *lookups: ProviderConfigReferenceLookup) -> None:
        if not lookups:
            raise ValueError("At least one provider-config reference lookup is required.")
        self._lookups = lookups

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for lookup in self._lookups:
            if await lookup.has_references(
                organization_id=organization_id,
                config_id=config_id,
            ):
                return True
        return False


__all__ = [
    "CombinedProviderConfigReferences",
    "MemoryDependencyReferenceLookup",
]
