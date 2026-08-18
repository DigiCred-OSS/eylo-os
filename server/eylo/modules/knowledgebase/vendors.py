"""Knowledge index catalog and executable metadata validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from eylo.common.contracts.knowledgebase import (
    DEFAULT_KNOWLEDGE_CHUNKING,
    DEFAULT_KNOWLEDGE_CHUNK_CHARS,
    DEFAULT_KNOWLEDGE_CHUNK_OVERLAP,
    MAX_KNOWLEDGE_CHUNK_CHARS,
    MIN_KNOWLEDGE_CHUNK_CHARS,
    KnowledgeChunkingStrategy,
)


@dataclass(frozen=True)
class VendorSpec:
    """A vendor, and the metadata keys it cannot run without."""

    name: str
    # Keys that must be present in the knowledgebase's metadata. Empty for a
    # vendor that needs nothing beyond a database connection.
    required_metadata: tuple[str, ...] = field(default_factory=tuple)

    # Whether this vendor needs an embedding provider to function. Checked
    # against the organization's configured capabilities at creation, because
    # the embedding model itself now lives there rather than in this
    # knowledgebase's metadata.
    needs_embeddings: bool = False
    description: str = ""


# The key a pgvector knowledgebase carries in its metadata. Required, with no
# default: the dimension of everything already stored depends on it, so a
# knowledgebase whose embedding model silently changed would return nonsense
# rather than an error.
EMBEDDING_MODEL_KEY = "embedding_model"

# Which chunking strategy a knowledgebase uses. Optional — paragraph packing is
# the stated default — but validated when present, because a typo here is a
# knowledgebase that fails its first ingestion rather than one that chunks
# slightly differently.
CHUNKING_KEY = "chunking"


class KnowledgebaseMetadata(BaseModel):
    """Complete, executable knowledgebase behavior configuration."""

    model_config = ConfigDict(extra="forbid")

    chunking: KnowledgeChunkingStrategy = DEFAULT_KNOWLEDGE_CHUNKING
    chunk_size: int = Field(
        default=DEFAULT_KNOWLEDGE_CHUNK_CHARS,
        strict=True,
        ge=MIN_KNOWLEDGE_CHUNK_CHARS,
        le=MAX_KNOWLEDGE_CHUNK_CHARS,
    )
    chunk_overlap: int = Field(
        default=DEFAULT_KNOWLEDGE_CHUNK_OVERLAP,
        strict=True,
        ge=0,
        lt=MAX_KNOWLEDGE_CHUNK_CHARS,
    )

    @model_validator(mode="after")
    def validate_window(self) -> KnowledgebaseMetadata:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


VENDORS: dict[str, VendorSpec] = {
    "postgres_fts": VendorSpec(
        name="postgres_fts",
        description="Keyword search over Postgres full-text indexes.",
    ),
    "pgvector": VendorSpec(
        name="pgvector",
        # No longer required here. The model lives on the embedding capability;
        # naming one in metadata is an override for a knowledgebase that has
        # already stored vectors from a particular model and must keep using
        # it.
        needs_embeddings=True,
        description="Semantic search over pgvector embeddings.",
    ),
}

KNOWN_VENDORS: tuple[str, ...] = tuple(sorted(VENDORS))


def needs_embeddings(vendor: str) -> bool:
    """Whether this vendor cannot function without an embedding provider."""
    spec = VENDORS.get(vendor)
    return bool(spec and spec.needs_embeddings)


def normalize_metadata(
    metadata: KnowledgebaseMetadata | dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the full persisted config or one stable operator-facing error."""
    try:
        parsed = KnowledgebaseMetadata.model_validate(metadata or {})
    except ValidationError as error:
        first = error.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"]) or "metadata"
        raise ValueError(
            f"Invalid knowledgebase metadata at {location}: {first['msg']}."
        ) from None
    return parsed.model_dump(mode="json")


def configuration_problem(
    vendor: str,
    metadata: KnowledgebaseMetadata | dict[str, Any] | None,
) -> str | None:
    """Why this configuration cannot work, or None if it can.

    Returns a sentence rather than raising, so the caller decides whether it is
    a 400 on the way in or a refusal at run time — the same check serves both,
    which is the point of it living here.

    This is the check that turns a permanent silent failure into an error an
    operator sees while they still have the form open.
    """
    spec = VENDORS.get(vendor)
    if spec is None:
        return (
            f"Unknown knowledgebase vendor '{vendor}'. "
            f"Available: {', '.join(KNOWN_VENDORS)}."
        )

    present = (
        metadata.model_dump(mode="json")
        if isinstance(metadata, KnowledgebaseMetadata)
        else (metadata or {})
    )
    if EMBEDDING_MODEL_KEY in present:
        return (
            "embedding_model metadata is unsupported. Select an explicit verified "
            "embedding_provider_config_id when creating a pgvector knowledgebase."
        )
    missing = [key for key in spec.required_metadata if not present.get(key)]
    if missing:
        return (
            f"The '{vendor}' vendor requires {', '.join(missing)} in metadata. "
            f"{spec.description}"
        )

    try:
        normalize_metadata(metadata)
    except ValueError as error:
        return str(error)
    return None
