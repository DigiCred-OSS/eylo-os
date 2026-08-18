"""Translate validated embedding domain config into socket runtime config."""

from __future__ import annotations

from eylo.modules.embedding_configs.catalog import EmbeddingProviders
from eylo.modules.embedding_configs.domain import (
    EmbeddingProviderConfig,
    ResolvedEmbedding,
)
from eylo.sockets.embedding.schemas import (
    BedrockEmbeddingConfig,
    EmbeddingConfig,
    EmbeddingRuntimeConfig,
)


def build_embedding_runtime_config(
    config: EmbeddingProviderConfig | ResolvedEmbedding,
) -> EmbeddingRuntimeConfig:
    if config.provider is EmbeddingProviders.BEDROCK:
        return BedrockEmbeddingConfig(
            model=config.model,
            region=config.region,
            dimensions=config.requested_dimensions,
            normalize=config.normalize,
            access_key_id=config.secret("access_key_id"),
            secret_access_key=config.secret("secret_access_key"),
            session_token=config.optional_secret("session_token"),
        )
    return EmbeddingConfig(
        model=config.model,
        api_key=config.secret("api_key"),
        base_url=config.base_url,
    )
