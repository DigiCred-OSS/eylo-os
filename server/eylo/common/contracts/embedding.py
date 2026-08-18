"""Vendor-neutral embedding types.

Embeddings are their own capability, not a corner of the LLM one. That was a
real defect before this existed: the embedder took whichever LLM provider was
default, read its API key, and called OpenAI's embeddings endpoint — so an
organization on Anthropic sent an Anthropic key to OpenAI, for an API Anthropic
does not offer at all. The same held for Groq, Cerebras, Sarvam and Bedrock.

A conversation model and an embedding model are different products from
different vendors with different keys. Treating them as one was the mistake.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class EmbeddingInput(StrEnum):
    """What a batch of text is *for*.

    OpenAI ignores this; Voyage and Cohere do not. Asymmetric embedding — where
    a query and a document are embedded differently — measurably improves
    retrieval on the vendors that support it, and a protocol that could not
    express it would quietly give up that gain.
    """

    DOCUMENT = "document"
    QUERY = "query"


class EmbeddingCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    asymmetric: bool = False
    max_batch: int = 96
    dimensions: int | None = None


class EmbeddingError(Exception):
    """An embedding call failed."""

    def __init__(
        self,
        message: str,
        *,
        vendor: str | None = None,
        code: str = "provider_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.code = code
        self.retryable = retryable


class EmbeddingConfig(BaseModel):
    """What a vendor needs to run.

    No defaults for `model`. Everything already stored was embedded with one,
    and a model that silently changed would make retrieval return nonsense
    rather than an error — the vectors would still compare, just meaninglessly.
    """

    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1, repr=False)
    base_url: str | None = None


class EmbeddingSpace(BaseModel):
    """Execution provenance plus one verified vector coordinate space."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    provider_config_id: UUID
    provider_config_revision: int = Field(gt=0)
    provider: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    model: str = Field(min_length=1)
    dimensions: int = Field(gt=0)
    semantic_options: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        # Provider-config authority answers which executable revision produced
        # a vector. It does not answer whether two vectors are comparable.
        # Only tenant isolation plus coordinate-affecting semantics belong in
        # this hash; credentials and display metadata therefore cannot split a
        # compatible store.
        canonical = json.dumps(
            {
                "organization_id": str(self.organization_id),
                "provider": self.provider,
                "endpoint": self.endpoint,
                "model": self.model,
                "dimensions": self.dimensions,
                "semantic_options": self.semantic_options,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def is_compatible_with(self, other: "EmbeddingSpace") -> bool:
        """Return whether vectors from both authorities may be compared."""
        return self.id == other.id


def embedding_space_from_record(record) -> EmbeddingSpace | None:
    """Rebuild and verify authority stamped on a durable vector owner/job."""
    return _embedding_space_from_record(record, prefix="embedding")


def target_embedding_space_from_record(record) -> EmbeddingSpace | None:
    """Rebuild a staged target authority without changing the active space."""
    return _embedding_space_from_record(record, prefix="target_embedding")


def source_embedding_space_from_record(record) -> EmbeddingSpace | None:
    """Rebuild the immutable source authority stamped on transition work."""
    return _embedding_space_from_record(record, prefix="source_embedding")


def _embedding_space_from_record(record, *, prefix: str) -> EmbeddingSpace | None:
    config_id = getattr(record, f"{prefix}_provider_config_id")
    if config_id is None:
        return None
    space = EmbeddingSpace(
        organization_id=record.organization_id,
        provider_config_id=config_id,
        provider_config_revision=getattr(
            record, f"{prefix}_provider_config_revision"
        ),
        provider=getattr(record, f"{prefix}_provider"),
        endpoint=getattr(record, f"{prefix}_endpoint"),
        model=getattr(record, f"{prefix}_model"),
        dimensions=getattr(record, f"{prefix}_dimensions"),
        semantic_options=getattr(record, f"{prefix}_semantic_options"),
    )
    if space.id != getattr(record, f"{prefix}_space_id"):
        raise ValueError("Persisted embedding authority has an invalid space ID.")
    return space
