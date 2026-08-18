"""pgvector as a knowledgebase vendor.

The semantic counterpart to `postgres_fts`. Same database, same chunking, same
contract — the difference is entirely in how a chunk is matched, which is
exactly the difference the protocol is designed to hide from callers and the
`capabilities` are designed to expose to them.

**Embeddings are this vendor's business.** The pipeline injects the exact
verified embedding revision pinned by the knowledgebase. Documents and queries
can use different provider intents, but every vector stays in one coordinate
space.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sql

from eylo.sockets.knowledgebase.base import KnowledgebaseVendorAdapter
from eylo.sockets.knowledgebase.schemas import (
    KnowledgeDocument,
    KnowledgeResult,
    KnowledgeScope,
    KnowledgebaseCapabilities,
    KnowledgebaseError,
)
from eylo.sockets.knowledgebase.vendors.postgres_base import (
    PostgresKnowledgebaseAuthority,
    chunk,
)

logger = logging.getLogger(__name__)

PROVIDER = "pgvector"


class PgVectorAdapter(KnowledgebaseVendorAdapter):
    """Semantic retrieval over `knowledge_chunks` using pgvector."""

    def __init__(
        self,
        session_factory,
        document_embedder,
        query_embedder,
        embedding_space_id: str,
        authority: PostgresKnowledgebaseAuthority,
        chunker=None,
    ) -> None:
        """Inject intent-specific embedders and one immutable vector space.

        Injected rather than constructed here because a socket may not reach
        into `modules/` to resolve provider authority.
        """
        self._session_factory = session_factory
        self._authority = authority
        # The knowledgebase's chunking strategy. None means paragraph packing.
        self._chunker = chunker
        self._document_embedder = document_embedder
        self._query_embedder = query_embedder
        self._embedding_space_id = embedding_space_id

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> KnowledgebaseCapabilities:
        return KnowledgebaseCapabilities(
            semantic_search=True,
            keyword_search=False,
            hybrid_search=False,
            metadata_filtering=True,
            single_document_delete=True,
        )

    async def ingest(self, document: KnowledgeDocument) -> str:
        if not self._authority.accepts_document(document):
            raise KnowledgebaseError(
                "Document authority does not match this knowledgebase.",
                vendor=PROVIDER,
            )
        chunks = chunk(document.content, self._chunker)
        if not chunks:
            raise KnowledgebaseError(
                "Document produced no content to index.", vendor=PROVIDER
            )

        vectors = await self._document_embedder(chunks)
        if len(vectors) != len(chunks):
            # A vendor returning fewer vectors than chunks would silently drop
            # content, and the gap would only show as a retrieval miss later.
            raise KnowledgebaseError(
                f"Embedder returned {len(vectors)} vectors for {len(chunks)} "
                "chunks; refusing to index a partial document.",
                vendor=PROVIDER,
            )

        # Derived, not generated. See KnowledgeDocument.identity — a random
        # id here would make every retry a duplicate.
        document_id = document.document_id
        async with self._session_factory() as session:
            await self._lock_active_space(session)
            # Delete-then-insert, in one transaction, keyed on the
            # document's derived identity. This is what makes ingest
            # idempotent: running it twice leaves exactly one copy, and a
            # crash leaves either the old version or the new one — never a
            # mix, and never both. A concurrent reader under READ COMMITTED
            # sees one complete version throughout, so a query during a
            # re-ingest cannot return half of each.
            await session.execute(
                sql(
                    "DELETE FROM knowledge_chunks "
                    "WHERE organization_id = :organization_id "
                    "AND knowledgebase_id = :knowledgebase_id "
                    "AND document_id = :document_id "
                    "AND embedding_space_id = :embedding_space_id"
                ),
                {
                    **self._authority.parameters,
                    "document_id": document_id,
                    "embedding_space_id": self._embedding_space_id,
                },
            )
            for position, (body, vector) in enumerate(zip(chunks, vectors)):
                await session.execute(
                    sql(
                        """
                        INSERT INTO knowledge_chunks
                            (id, organization_id, knowledgebase_id, document_id,
                             scope, scope_id, position, content, title,
                             source_uri, meta, embedding, embedding_space_id)
                        VALUES
                            (gen_random_uuid(), :organization_id,
                             :knowledgebase_id, :document_id, :scope, :scope_id,
                             :position, :content, :title, :source_uri,
                             CAST(:meta AS jsonb), CAST(:embedding AS vector),
                             :embedding_space_id)
                        """
                    ),
                    {
                        "document_id": document_id,
                        **self._authority.parameters,
                        "position": position,
                        "content": body,
                        "title": document.title,
                        "source_uri": document.source_uri,
                        "meta": _json(document.metadata),
                        "embedding": _vector(vector),
                        "embedding_space_id": self._embedding_space_id,
                    },
                )
            await session.commit()

        logger.info(
            "Embedded document %s as %d chunk(s) in knowledgebase %s",
            document_id,
            len(chunks),
            self._authority.knowledgebase_id,
        )
        return document_id

    async def query(
        self,
        text_query: str,
        *,
        scopes: dict[KnowledgeScope, str],
        limit: int = 5,
    ) -> list[KnowledgeResult]:
        # Same rule as every vendor: no scopes means no grants means no
        # knowledge. A missing filter must never widen access.
        if not text_query.strip() or not self._authority.is_requested(scopes):
            return []

        vector = await self._query_embedder(text_query)

        async with self._session_factory() as session:
            await self._lock_active_space(session)
            rows = await session.execute(
                sql(
                    """
                    SELECT chunks.document_id, chunks.content, chunks.title,
                           chunks.source_uri, chunks.meta, chunks.scope,
                           chunks.scope_id,
                           chunks.embedding <=> CAST(:embedding AS vector)
                               AS distance
                    FROM knowledge_chunks AS chunks
                    JOIN knowledgebases AS knowledgebase
                      ON knowledgebase.id = chunks.knowledgebase_id
                     AND knowledgebase.organization_id = chunks.organization_id
                     AND knowledgebase.deleted IS FALSE
                    WHERE chunks.organization_id = :organization_id
                      AND chunks.knowledgebase_id = :knowledgebase_id
                      AND chunks.scope = :scope
                      AND chunks.scope_id = :scope_id
                      AND chunks.deleted IS FALSE
                      AND chunks.embedding IS NOT NULL
                      AND chunks.embedding_space_id = :embedding_space_id
                    ORDER BY distance ASC
                    LIMIT :limit
                    """
                ),
                {
                    **self._authority.parameters,
                    "embedding": _vector(vector),
                    "embedding_space_id": self._embedding_space_id,
                    "limit": limit,
                },
            )
            return [
                KnowledgeResult(
                    document_id=str(row.document_id),
                    content=row.content,
                    # Cosine distance inverted so higher is better, matching
                    # every other vendor's direction. Still not comparable with
                    # an FTS rank — same direction, different meaning.
                    score=1.0 - float(row.distance),
                    scope=KnowledgeScope(row.scope),
                    scope_id=row.scope_id,
                    title=row.title,
                    source_uri=row.source_uri,
                    metadata=row.meta or {},
                )
                for row in rows
            ]

    async def delete(self, document_id: str) -> bool:
        async with self._session_factory() as session:
            await self._lock_active_space(session)
            result = await session.execute(
                sql(
                    "DELETE FROM knowledge_chunks WHERE document_id = :id "
                    "AND organization_id = :organization_id "
                    "AND knowledgebase_id = :knowledgebase_id "
                    "AND embedding_space_id = :embedding_space_id"
                ),
                {
                    **self._authority.parameters,
                    "id": document_id,
                    "embedding_space_id": self._embedding_space_id,
                },
            )
            await session.commit()
            return bool(result.rowcount)

    async def _lock_active_space(self, session) -> None:
        active_space_id = await session.scalar(
            sql(
                """
                SELECT embedding_space_id
                FROM knowledgebases
                WHERE id = :knowledgebase_id
                  AND organization_id = :organization_id
                  AND deleted IS FALSE
                FOR SHARE
                """
            ),
            self._authority.parameters,
        )
        if active_space_id is None:
            raise KnowledgebaseError("Knowledgebase is no longer available.")
        if active_space_id != self._embedding_space_id:
            raise KnowledgebaseError(
                "Knowledgebase embedding space changed; retry the operation.",
                vendor=PROVIDER,
                retryable=True,
            )


def _vector(values) -> str:
    """Pgvector's literal form."""
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value or {})
