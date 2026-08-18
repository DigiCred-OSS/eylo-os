"""Embedding runtime composition."""

from eylo.pipelines.embedding.resolver import (
    EmbeddingRuntime,
    resolve_embedding_runtime,
    resolve_pinned_embedding_runtime,
)

__all__ = [
    "EmbeddingRuntime",
    "resolve_embedding_runtime",
    "resolve_pinned_embedding_runtime",
]
