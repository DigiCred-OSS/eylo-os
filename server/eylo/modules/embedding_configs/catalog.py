"""Embedding config catalog."""

from __future__ import annotations

from enum import Enum

BEDROCK_EMBEDDING_MODELS = ("amazon.titan-embed-text-v2:0",)
BEDROCK_EMBEDDING_DIMENSIONS = (256, 512, 1024)

__all__ = [
    "BEDROCK_EMBEDDING_DIMENSIONS",
    "BEDROCK_EMBEDDING_MODELS",
    "EmbeddingProviders",
]


class EmbeddingProviders(str, Enum):
    BEDROCK = "bedrock"
    # OpenAI, and every gateway that speaks its shape — Ollama, vLLM, TEI,
    # LiteLLM, Azure. One entry covers the hosted and the self-hosted path,
    # which is what `base_url` is for.
    OPENAI = "openai"
    # Anthropic has no embeddings API and points customers here, so an
    # organization running Claude has no other option.
    VOYAGE = "voyage"
