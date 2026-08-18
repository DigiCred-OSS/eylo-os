"""Compose knowledgebase domain configuration with vendor adapters."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.embedding import (
    EmbeddingError,
    embedding_space_from_record,
)
from eylo.common.contracts.knowledgebase import KnowledgeScope
from eylo.common.contracts.knowledgebase import (
    KnowledgebaseError as KnowledgebaseOperationError,
)
from eylo.common.database import async_session_factory
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.knowledgebase.services.knowledgebases import KnowledgebaseError
from eylo.modules.knowledgebase.vendors import (
    CHUNKING_KEY,
    configuration_problem,
    normalize_metadata,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.resolver import (
    resolve_compatible_embedding_runtime,
    resolve_pinned_embedding_runtime,
)
from eylo.sockets.knowledgebase.base import KnowledgebaseVendorAdapter
from eylo.sockets.knowledgebase.chunking import build_chunker
from eylo.sockets.knowledgebase.vendors.pgvector import PgVectorAdapter
from eylo.sockets.knowledgebase.vendors.postgres_base import (
    PostgresKnowledgebaseAuthority,
)
from eylo.sockets.knowledgebase.vendors.postgres_fts import PostgresFTSAdapter


async def resolve_adapter(
    knowledgebase,
    *,
    organization_id: UUID,
    session: AsyncSession,
    embedding_authority=None,
) -> KnowledgebaseVendorAdapter:
    """Build the adapter named by one organization-owned knowledgebase."""
    if str(knowledgebase.organization_id) != str(organization_id):
        raise KnowledgebaseError("Knowledgebase not found.")

    vendor = knowledgebase.vendor
    chunker = _build_chunker(knowledgebase)
    authority = PostgresKnowledgebaseAuthority(
        organization_id=UUID(str(organization_id)),
        knowledgebase_id=UUID(str(knowledgebase.id)),
        scope=KnowledgeScope(knowledgebase.scope),
        scope_id=knowledgebase.scope_id,
    )

    if vendor == "postgres_fts":
        return PostgresFTSAdapter(async_session_factory, authority, chunker)

    if vendor == "pgvector":
        runtime = await _embedding_runtime(
            embedding_authority if embedding_authority is not None else knowledgebase,
            organization_id=organization_id,
            session=session,
            exact_revision=embedding_authority is not None,
        )
        document_embedder, query_embedder = _embedding_functions(runtime)
        return PgVectorAdapter(
            async_session_factory,
            document_embedder,
            query_embedder,
            runtime.space.id,
            authority,
            chunker,
        )

    raise KnowledgebaseError(
        configuration_problem(vendor, knowledgebase.meta)
        or f"Vendor '{vendor}' has no adapter."
    )


def _build_chunker(knowledgebase):
    try:
        meta = normalize_metadata(knowledgebase.meta)
    except ValueError as error:
        raise KnowledgebaseError(str(error)) from None
    return build_chunker(
        meta.get(CHUNKING_KEY),
        size=meta.get("chunk_size"),
        overlap=meta.get("chunk_overlap"),
    )


async def _embedding_runtime(
    knowledgebase,
    *,
    organization_id: UUID,
    session,
    exact_revision: bool,
):
    try:
        persisted_space = embedding_space_from_record(knowledgebase)
    except ValueError:
        raise KnowledgebaseOperationError(
            "Persisted knowledgebase embedding authority is invalid."
        ) from None
    if persisted_space is None:
        raise KnowledgebaseOperationError(
            "pgvector knowledgebase has no immutable embedding space."
        )
    try:
        if exact_revision:
            runtime = await resolve_pinned_embedding_runtime(
                organization_id,
                provider_config_id=persisted_space.provider_config_id,
                provider_config_revision=persisted_space.provider_config_revision,
                db=session,
            )
        else:
            runtime = await resolve_compatible_embedding_runtime(
                organization_id,
                persisted_space=persisted_space,
                db=session,
            )
    except (InvalidEmbeddingConfig, NotConfiguredError):
        raise KnowledgebaseOperationError(
            "Pinned knowledgebase embedding authority is unavailable."
        ) from None
    if not runtime.space.is_compatible_with(persisted_space):
        raise KnowledgebaseOperationError(
            "pgvector knowledgebase embedding authority does not match its space."
        )
    return runtime


def _embedding_functions(runtime):
    async def embed_documents(texts: list[str]) -> list[list[float]]:
        try:
            return await runtime.embed_documents(texts)
        except EmbeddingError as error:
            raise KnowledgebaseOperationError(
                "Knowledgebase embedding failed.",
                vendor=error.vendor,
                retryable=error.retryable,
            ) from None

    async def embed_query(text: str) -> list[float]:
        try:
            return await runtime.embed_query(text)
        except EmbeddingError as error:
            raise KnowledgebaseOperationError(
                "Knowledgebase query embedding failed.",
                vendor=error.vendor,
                retryable=error.retryable,
            ) from None

    return embed_documents, embed_query
