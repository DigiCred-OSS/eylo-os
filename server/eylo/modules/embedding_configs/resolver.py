"""Resolve one explicit organization embedding config or pinned revision."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.embedding_configs.domain import (
    InvalidEmbeddingConfig,
    ResolvedEmbedding,
)
from eylo.modules.embedding_configs.service import EmbeddingConfigService
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError

__all__ = ["EmbeddingConfigResolver"]


class EmbeddingConfigResolver:
    def __init__(self, configs: EmbeddingConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedEmbedding:
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
    ) -> ResolvedEmbedding:
        effective = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        return self._to_resolved(effective, organization_id)

    def _to_resolved(self, effective, organization_id: UUID) -> ResolvedEmbedding:
        try:
            return ResolvedEmbedding.from_provider_config(
                provider_config_id=effective.provider_config_id,
                organization_id=organization_id,
                provider_config=effective,
                endpoint_policy=self._configs.endpoint_policy,
            )
        except InvalidEmbeddingConfig:
            raise _not_configured("valid_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.EMBEDDING,
        missing=[missing],
        configure_via="/api/embedding-configs",
    )
