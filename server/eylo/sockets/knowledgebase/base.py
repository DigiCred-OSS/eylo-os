"""Provider-neutral contracts for the `knowledgebase` socket."""

from __future__ import annotations

from abc import ABC, abstractmethod

from eylo.sockets.knowledgebase.schemas import (
    KnowledgeDocument,
    KnowledgeResult,
    KnowledgeScope,
    KnowledgebaseCapabilities,
)


class KnowledgebaseVendorAdapter(ABC):
    """One knowledgebase vendor.

    Every method is document-level. Nothing here mentions chunks, embeddings,
    indexes or similarity — those are vendor concerns, and naming one would put
    it in the contract for vendors that do not have it.
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """Vendor name, for errors and reporting."""

    @property
    @abstractmethod
    def capabilities(self) -> KnowledgebaseCapabilities:
        """What this vendor does. Callers branch on it rather than assuming."""

    @abstractmethod
    async def ingest(self, document: KnowledgeDocument) -> str:
        """Store a document and return its id.

        The vendor chunks, embeds and indexes however it chooses. Slow by
        nature — parsing and embedding do not belong on a conversational turn,
        so callers dispatch this rather than awaiting it inline.
        """

    @abstractmethod
    async def query(
        self,
        text: str,
        *,
        scopes: dict[KnowledgeScope, str],
        limit: int = 5,
    ) -> list[KnowledgeResult]:
        """Retrieve documents, most relevant first.

        `scopes` maps each scope the caller wants searched to its id — the
        agent chooses which, and results come back ranked together in one list
        rather than grouped. An empty mapping searches nothing and returns
        nothing, which is correct: an agent with no knowledge grants has no
        knowledge, and that is not an error.
        """

    @abstractmethod
    async def delete(self, document_id: str) -> bool:
        """Remove one document. True only when it is gone.

        False rather than an exception when the vendor cannot delete singly —
        `capabilities.single_document_delete` says so in advance, and a caller
        that ignored it should get a usable answer rather than a crash.
        """

    async def write(self, document: KnowledgeDocument) -> str:
        """Store a document an agent produced, rather than one a source supplied.

        Concrete, delegating to `ingest`, because for most vendors there is no
        difference in storage — the difference is in permission, and that is
        enforced before this is reached. A vendor that does treat them
        differently overrides this.
        """
        return await self.ingest(document)
