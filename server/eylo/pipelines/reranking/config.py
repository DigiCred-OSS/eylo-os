"""Translate validated reranking domain config into socket runtime config."""

from __future__ import annotations

from eylo.modules.reranking_configs.catalog import RerankingProviders
from eylo.modules.reranking_configs.domain import (
    RerankingProviderConfig,
    ResolvedReranking,
)
from eylo.sockets.reranking.schemas import (
    BedrockRerankingConfig,
    RerankingConfig,
    RerankingRuntimeConfig,
)


def build_reranking_runtime_config(
    config: RerankingProviderConfig | ResolvedReranking,
) -> RerankingRuntimeConfig:
    if config.provider is RerankingProviders.BEDROCK:
        return BedrockRerankingConfig(
            model=config.model,
            region=config.region,
            access_key_id=config.secret("access_key_id"),
            secret_access_key=config.secret("secret_access_key"),
            session_token=config.optional_secret("session_token"),
        )
    return RerankingConfig(
        model=config.model,
        api_key=config.secret("api_key"),
        base_url=config.endpoint,
    )
