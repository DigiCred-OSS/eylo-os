"""Resolve one explicit organization memory config or pinned revision."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.memory_configs.domain import InvalidMemoryConfig, ResolvedMemory
from eylo.modules.memory_configs.service import MemoryConfigService
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError

__all__ = ["MemoryConfigResolver"]


class MemoryConfigResolver:
    def __init__(self, configs: MemoryConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedMemory:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        effective = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        return self._to_resolved(effective)

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedMemory:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return self._to_resolved(effective)

    @staticmethod
    def _to_resolved(effective) -> ResolvedMemory:
        try:
            return ResolvedMemory.from_effective(effective)
        except InvalidMemoryConfig:
            raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.MEMORY,
        missing=[missing],
        configure_via="/api/memory-configs",
    )
