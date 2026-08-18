"""Resolve one explicit organization sandbox config or pinned revision."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.sandbox_configs.domain import InvalidSandboxConfig, ResolvedSandbox
from eylo.modules.sandbox_configs.service import SandboxConfigService

__all__ = ["SandboxConfigResolver"]


class SandboxConfigResolver:
    def __init__(self, configs: SandboxConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedSandbox:
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
    ) -> ResolvedSandbox:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return self._to_resolved(effective)

    @staticmethod
    def _to_resolved(effective) -> ResolvedSandbox:
        try:
            return ResolvedSandbox.from_effective(effective)
        except InvalidSandboxConfig:
            raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.SANDBOX,
        missing=[missing],
        configure_via="/api/sandbox-configs",
    )
