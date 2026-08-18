"""Postgres full-text search as a knowledgebase vendor.

The vendor with **no embeddings at all**, which is why it ships in V1 alongside
pgvector rather than after it: a protocol both satisfy cannot have leaked an
embedding assumption into itself. It is the honesty check on the contract.

What it gives up is stated rather than discovered. `capabilities.semantic_search`
is false — this matches words, not meaning, so a query phrased differently from
the document will miss. An operator choosing FTS is choosing no embedding
infrastructure and accepting that.
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

PROVIDER = "postgres-fts"


class PostgresFTSAdapter(KnowledgebaseVendorAdapter):
    """Keyword retrieval over `knowledge_chunks` using Postgres tsvector."""

    def __init__(
        self,
        session_factory,
        authority: PostgresKnowledgebaseAuthority,
        chunker=None,
    ) -> None:
        # A factory rather than a session: ingestion runs on a worker and query
        # runs on a turn, and they must not share a transaction.
        self._session_factory = session_factory
        self._authority = authority
        # The knowledgebase's chunking strategy. None means paragraph packing.
        self._chunker = chunker

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> KnowledgebaseCapabilities:
        return KnowledgebaseCapabilities(
            semantic_search=False,
            keyword_search=True,
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

        # Derived, not generated. See KnowledgeDocument.identity — a random
        # id here would make every retry a duplicate.
        document_id = document.document_id
        async with self._session_factory() as session:
            await self._authority.lock_live(session)
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
                    "AND document_id = :document_id"
                ),
                {**self._authority.parameters, "document_id": document_id},
            )
            for position, body in enumerate(chunks):
                await session.execute(
                    sql(
                        """
                        INSERT INTO knowledge_chunks
                            (id, organization_id, knowledgebase_id, document_id,
                             scope, scope_id, position, content, title,
                             source_uri, meta, search_vector)
                        VALUES
                            (gen_random_uuid(), :organization_id,
                             :knowledgebase_id, :document_id, :scope, :scope_id,
                             :position, :content, :title, :source_uri,
                             CAST(:meta AS jsonb),
                             to_tsvector('english', :content))
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
                    },
                )
            await session.commit()

        logger.info(
            "Indexed document %s as %d chunk(s) in knowledgebase %s",
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
        # No scopes means no grants, which means no knowledge. Returning empty
        # rather than querying everything is the whole point of the scoping
        # model — a missing filter must never widen access.
        if not text_query.strip() or not self._authority.is_requested(scopes):
            return []

        async with self._session_factory() as session:
            rows = await session.execute(
                sql(
                    """
                    SELECT chunks.document_id, chunks.content, chunks.title,
                           chunks.source_uri, chunks.meta, chunks.scope,
                           chunks.scope_id,
                           ts_rank(chunks.search_vector,
                                   plainto_tsquery('english', :q))
                               AS score
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
                      AND chunks.search_vector @@ plainto_tsquery('english', :q)
                    ORDER BY score DESC
                    LIMIT :limit
                    """
                ),
                {
                    **self._authority.parameters,
                    "q": text_query,
                    "limit": limit,
                },
            )
            return [
                KnowledgeResult(
                    document_id=str(row.document_id),
                    content=row.content,
                    # A ts_rank, not a distance. Not comparable with pgvector's
                    # score — the contract says so rather than normalising and
                    # inventing a precision neither has.
                    score=float(row.score),
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
            result = await session.execute(
                sql(
                    "DELETE FROM knowledge_chunks "
                    "WHERE organization_id = :organization_id "
                    "AND knowledgebase_id = :knowledgebase_id "
                    "AND document_id = :id"
                ),
                {
                    **self._authority.parameters,
                    "id": document_id,
                },
            )
            await session.commit()
            return bool(result.rowcount)


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value or {})
