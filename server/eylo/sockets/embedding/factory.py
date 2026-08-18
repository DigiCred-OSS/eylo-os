"""Construct one embedding adapter from validated runtime config."""

from __future__ import annotations

from eylo.sockets.embedding.base import EmbeddingVendorAdapter
from eylo.sockets.embedding.schemas import (
    BedrockEmbeddingConfig,
    EmbeddingConfig,
    EmbeddingRuntimeConfig,
)
from eylo.sockets.embedding.vendors.bedrock import BedrockEmbeddingAdapter
from eylo.sockets.embedding.vendors.openai import OpenAIEmbeddingAdapter
from eylo.sockets.embedding.vendors.voyage import VoyageEmbeddingAdapter


class EmbeddingFactory:
    def __init__(self, provider: str, config: EmbeddingRuntimeConfig) -> None:
        self._provider = provider.strip().lower()
        self._config = config

    def get_adapter(self) -> EmbeddingVendorAdapter:
        if self._provider == "bedrock":
            if not isinstance(self._config, BedrockEmbeddingConfig):
                raise ValueError("Bedrock embedding config is invalid.")
            return BedrockEmbeddingAdapter(self._config)
        if not isinstance(self._config, EmbeddingConfig):
            raise ValueError("API-key embedding config is invalid.")
        if self._provider == "openai":
            return OpenAIEmbeddingAdapter(self._config)
        if self._provider == "voyage":
            return VoyageEmbeddingAdapter(self._config)
        raise ValueError("Embedding provider is not supported.")
