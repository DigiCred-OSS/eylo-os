"""Construct one reranking adapter from validated runtime config."""

from __future__ import annotations

from eylo.sockets.reranking.base import RerankingVendorAdapter
from eylo.sockets.reranking.schemas import (
    BedrockRerankingConfig,
    RerankingConfig,
    RerankingRuntimeConfig,
)
from eylo.sockets.reranking.vendors.bedrock import BedrockRerankAdapter
from eylo.sockets.reranking.vendors.cohere import CohereRerankAdapter
from eylo.sockets.reranking.vendors.voyage import VoyageRerankAdapter


class RerankingFactory:
    def __init__(self, provider: str, config: RerankingRuntimeConfig) -> None:
        self._provider = provider.strip().lower()
        self._config = config

    def get_adapter(self) -> RerankingVendorAdapter:
        if self._provider == "bedrock":
            if not isinstance(self._config, BedrockRerankingConfig):
                raise ValueError("Bedrock reranking config is invalid.")
            return BedrockRerankAdapter(self._config)
        if not isinstance(self._config, RerankingConfig):
            raise ValueError("API-key reranking config is invalid.")
        if self._provider == "cohere":
            return CohereRerankAdapter(self._config)
        if self._provider == "voyage":
            return VoyageRerankAdapter(self._config)
        raise ValueError("Reranking provider is not supported.")
