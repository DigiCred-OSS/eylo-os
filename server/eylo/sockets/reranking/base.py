"""The reranking vendor contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from eylo.sockets.reranking.schemas import RerankResult, RerankingCapabilities


class RerankingVendorAdapter(ABC):
    """Reordering retrieved candidates by relevance to a query."""

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> RerankingCapabilities: ...

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[str], *, top_k: int
    ) -> list[RerankResult]:
        """The best `top_k` of `documents`, most relevant first.

        Results carry indices into `documents`, so a caller keeps its own
        objects and their provenance.

        **A vendor must never invent an index.** The adapter rejects the entire
        response when any index is duplicated, out of range, or paired with a
        non-finite score. Partial external results are not valid rankings.
        """
        ...
