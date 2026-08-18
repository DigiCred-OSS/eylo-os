"""Resolve one explicit, verified embedding revision into a vector space."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from eylo.common.contracts.embedding import (
    EmbeddingError,
    EmbeddingInput,
    EmbeddingSpace,
)
from eylo.modules.embedding_configs.domain import (
    InvalidEmbeddingConfig,
    ResolvedEmbedding,
)
from eylo.modules.embedding_configs.wiring import build_embedding_config_resolver
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.config import build_embedding_runtime_config
from eylo.sockets.embedding.base import EmbeddingVendorAdapter
from eylo.sockets.embedding.factory import EmbeddingFactory


@dataclass(frozen=True)
class EmbeddingRuntime:
    """Adapter plus the immutable coordinate space it is allowed to use."""

    space: EmbeddingSpace
    adapter: EmbeddingVendorAdapter

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._require_space(
            await self.adapter.embed(texts, input_type=EmbeddingInput.DOCUMENT)
        )

    async def embed_query(self, text: str) -> list[float]:
        vectors = self._require_space(
            await self.adapter.embed([text], input_type=EmbeddingInput.QUERY)
        )
        return vectors[0]

    def _require_space(self, vectors: list[list[float]]) -> list[list[float]]:
        if any(len(vector) != self.space.dimensions for vector in vectors):
            raise EmbeddingError(
                "Embedding vector dimensions do not match the verified space.",
                vendor=self.space.provider,
                code="dimension_mismatch",
            )
        return vectors


async def resolve_embedding_runtime(
    organization_id: UUID,
    *,
    provider_config_id: UUID,
    db=None,
) -> EmbeddingRuntime:
    """Resolve the current verified revision selected by the caller."""
    resolved = await build_embedding_config_resolver(db).resolve(
        organization_id,
        provider_config_id=provider_config_id,
    )
    return _build_runtime(resolved)


async def resolve_pinned_embedding_runtime(
    organization_id: UUID,
    *,
    provider_config_id: UUID,
    provider_config_revision: int,
    db=None,
) -> EmbeddingRuntime:
    """Resolve the exact revision recorded by durable vector work."""
    resolved = await build_embedding_config_resolver(db).resolve_pinned(
        organization_id,
        provider_config_id=provider_config_id,
        revision=provider_config_revision,
    )
    return _build_runtime(resolved)


async def resolve_compatible_embedding_runtime(
    organization_id: UUID,
    *,
    persisted_space: EmbeddingSpace,
    db=None,
) -> EmbeddingRuntime:
    """Prefer current ready credentials, then fall back to recorded execution."""
    if persisted_space.organization_id != organization_id:
        raise InvalidEmbeddingConfig(
            "Embedding space does not belong to the requested organization."
        )

    try:
        current = await resolve_embedding_runtime(
            organization_id,
            provider_config_id=persisted_space.provider_config_id,
            db=db,
        )
    except (InvalidEmbeddingConfig, NotConfiguredError):
        current = None
    if current is not None and current.space.is_compatible_with(persisted_space):
        return current

    pinned = await resolve_pinned_embedding_runtime(
        organization_id,
        provider_config_id=persisted_space.provider_config_id,
        provider_config_revision=persisted_space.provider_config_revision,
        db=db,
    )
    if not pinned.space.is_compatible_with(persisted_space):
        raise InvalidEmbeddingConfig(
            "Recorded embedding execution does not match its semantic space."
        )
    return pinned


def _build_runtime(resolved: ResolvedEmbedding) -> EmbeddingRuntime:
    adapter = EmbeddingFactory(
        resolved.provider.value,
        build_embedding_runtime_config(resolved),
    ).get_adapter()
    space = _build_space(resolved, semantic_options=adapter.semantic_options)
    return EmbeddingRuntime(space=space, adapter=adapter)


def _build_space(
    resolved: ResolvedEmbedding,
    *,
    semantic_options: dict[str, object],
) -> EmbeddingSpace:
    metadata = resolved.verification_metadata
    if metadata.get("endpoint") != resolved.endpoint:
        raise InvalidEmbeddingConfig(
            "Verified embedding endpoint does not match the resolved revision."
        )
    if metadata.get("model") != resolved.model:
        raise InvalidEmbeddingConfig(
            "Verified embedding model does not match the resolved revision."
        )
    return EmbeddingSpace(
        organization_id=resolved.organization_id,
        provider_config_id=resolved.provider_config_id,
        provider_config_revision=resolved.provider_config_revision,
        provider=resolved.provider.value,
        endpoint=resolved.endpoint,
        model=resolved.model,
        dimensions=resolved.dimensions,
        semantic_options=semantic_options,
    )
