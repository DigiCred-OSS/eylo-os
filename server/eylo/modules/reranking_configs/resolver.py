"""Resolve one explicit organization reranking config or pinned revision."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.reranking_configs.domain import (
    InvalidRerankingConfig,
    ResolvedReranking,
)
from eylo.modules.reranking_configs.service import RerankingConfigService

__all__ = ["RerankingConfigResolver"]


class RerankingConfigResolver:
    def __init__(self, configs: RerankingConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedReranking:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        effective = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        return self._to_resolved(effective, organization_id)

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedReranking:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return self._to_resolved(effective, organization_id)

    def _to_resolved(self, effective, organization_id: UUID) -> ResolvedReranking:
        try:
            return ResolvedReranking.from_provider_config(
                provider_config_id=effective.provider_config_id,
                organization_id=organization_id,
                provider_config=effective,
                endpoint_policy=self._configs.endpoint_policy,
            )
        except InvalidRerankingConfig:
            raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.RERANKING,
        missing=[missing],
        configure_via="/api/reranking-configs",
    )
