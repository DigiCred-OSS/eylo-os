"""Reranking config catalog."""

from __future__ import annotations

from enum import Enum

BEDROCK_RERANKING_MODELS = (
    "amazon.rerank-v1:0",
    "cohere.rerank-v3-5:0",
)
BEDROCK_RERANKING_REGIONS = {
    "amazon.rerank-v1:0": frozenset(
        {"ap-northeast-1", "ca-central-1", "eu-central-1", "us-west-2"}
    ),
    "cohere.rerank-v3-5:0": frozenset(
        {
            "ap-northeast-1",
            "ca-central-1",
            "eu-central-1",
            "us-east-1",
            "us-west-2",
        }
    ),
}

__all__ = [
    "BEDROCK_RERANKING_MODELS",
    "BEDROCK_RERANKING_REGIONS",
    "RerankingProviders",
]


class RerankingProviders(str, Enum):
    BEDROCK = "bedrock"
    # The most widely used hosted reranker, and the shape most compatible
    # gateways imitate — which is what `base_url` reaches.
    COHERE = "cohere"
    # Pairs with the Voyage embedder. Anthropic offers neither embeddings nor
    # reranking, so without this an organization on Claude has retrieval
    # quality it cannot improve.
    VOYAGE = "voyage"
