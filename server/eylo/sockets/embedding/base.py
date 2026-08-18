"""The embedding vendor contract.

One verb. Everything a caller needs from an embedding vendor is "turn this text
into vectors", and every difference between vendors that matters — batch
limits, whether queries embed differently from documents — is reported through
`capabilities` rather than expressed as extra methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from eylo.sockets.embedding.schemas import (
    EmbeddingCapabilities,
    EmbeddingInput,
    EmbeddingSemanticOptions,
)


class EmbeddingVendorAdapter(ABC):
    """Text to vectors."""

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> EmbeddingCapabilities: ...

    @property
    @abstractmethod
    def semantic_options(self) -> EmbeddingSemanticOptions:
        """Canonical vendor-owned settings that affect vector coordinates."""
        ...

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInput = EmbeddingInput.DOCUMENT,
    ) -> list[list[float]]:
        """Vectors for `texts`, in the same order.

        **Order is part of the contract.** Callers pair the result with their
        input positionally, so a vendor that returns results out of order would
        attach every chunk to the wrong vector — a failure that looks like poor
        retrieval rather than a bug, and would take a long time to find.

        Returning fewer vectors than inputs must raise rather than truncate,
        for the same reason.

        `input_type` is honoured by vendors whose `capabilities.asymmetric` is
        true and ignored by the rest. Passing it is always safe.
        """
        ...
