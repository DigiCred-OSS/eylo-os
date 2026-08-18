"""Vendor-neutral reranking types.

Retrieval embeds a query and a document independently. A reranker scores the
pair together, so it reorders over-fetched retrieval candidates rather than
replacing retrieval.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RankingState(StrEnum):
    NOT_REQUESTED = "not_requested"
    APPLIED = "applied"
    DEGRADED = "degraded"


class RankingMetadata(BaseModel):
    """Visible outcome of the optional reranking stage."""

    model_config = ConfigDict(extra="forbid")

    state: RankingState
    comparable: bool
    reason: str | None = None
    provider: str | None = None
    provider_config_id: UUID | None = None
    provider_config_revision: int | None = Field(default=None, gt=0)
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)


class RerankResult(BaseModel):
    """One candidate's placement.

    Carries the **index into the caller's list**, not the text. The caller
    already holds the full objects — content, source, scope, which
    knowledgebase it came from — and shuttling those through a vendor and back
    would mean reconstructing them by string matching on the way out.
    """

    model_config = ConfigDict(extra="forbid")

    index: int
    score: float = Field(allow_inf_nan=False)


class RerankingCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    max_documents: int = 100
    truncates: bool = True


class RerankingConfig(BaseModel):
    """What a vendor needs to run."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1, max_length=8192, repr=False)
    base_url: str | None = Field(default=None, max_length=2048)

    @field_validator("model", "api_key")
    @classmethod
    def validate_single_line(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(character in normalized for character in "\x00\r\n"):
            raise ValueError("Value must be a non-empty single-line string.")
        return normalized


class RerankingError(Exception):
    """A rerank call failed.

    `retryable` matters more here than elsewhere: reranking sits on a
    conversation turn, and a caller that cannot rerank should return the
    retrieval order rather than fail the turn.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        vendor: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.vendor = vendor
        self.retryable = retryable
