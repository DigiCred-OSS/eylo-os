"""Shared pipeline for the Postgres-backed knowledgebase vendors.

pgvector and full-text search differ in how they *retrieve*, not in how they
receive a document — both take text, split it, and store rows against a scope.
That shared work lives here.

**Inside `vendors/`, deliberately, not in the socket.** What pgvector and a
hosted RAG vendor have in common is the protocol; what pgvector and FTS have in
common is a database. Putting this in the ABC would push a chunking strategy
onto vendors that own their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text as sql

from eylo.sockets.knowledgebase.schemas import (
    KnowledgeDocument,
    KnowledgeScope,
    KnowledgebaseError,
)


@dataclass(frozen=True, slots=True)
class PostgresKnowledgebaseAuthority:
    """The exact tenant partition one Postgres adapter may access."""

    organization_id: UUID
    knowledgebase_id: UUID
    scope: KnowledgeScope
    scope_id: str

    def accepts_document(self, document: KnowledgeDocument) -> bool:
        return (
            document.scope is self.scope
            and document.scope_id == self.scope_id
        )

    def is_requested(self, scopes: dict[KnowledgeScope, str]) -> bool:
        return scopes.get(self.scope) == self.scope_id

    async def lock_live(self, session) -> None:
        """Hold deletion behind an in-flight replacement transaction."""
        live = await session.scalar(
            sql(
                """
                SELECT id
                FROM knowledgebases
                WHERE id = :knowledgebase_id
                  AND organization_id = :organization_id
                  AND deleted IS FALSE
                FOR SHARE
                """
            ),
            self.parameters,
        )
        if live is None:
            raise KnowledgebaseError("Knowledgebase is no longer available.")

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "knowledgebase_id": self.knowledgebase_id,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
        }


def chunk(text: str, strategy=None) -> list[str]:
    """Split a document using the knowledgebase's chosen strategy.

    Kept as a function so existing callers do not change, but the behaviour is
    now a choice: `strategy` is a `ChunkingStrategy` built from the
    knowledgebase's config. Passing None gives paragraph packing, which is what
    this always did.

    See `sockets/knowledgebase/chunking/` for why there are three strategies
    and why they live beside the Postgres vendors rather than in the ABC.
    """
    from eylo.sockets.knowledgebase.chunking import build_chunker

    return (strategy or build_chunker()).chunk(text)
