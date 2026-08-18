"""One bounded, failure-visible reranking stage for retrieval pipelines."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from eylo.common.contracts.reranking import (
    RankingMetadata,
    RankingState,
    RerankResult,
    RerankingError,
)
from eylo.pipelines.reranking.resolver import RerankingRuntime

logger = logging.getLogger(__name__)

MAX_RERANK_CHARACTERS = 200_000
RERANK_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class BoundedRerankingOutcome:
    """Validated selections, or ``None`` when retrieval order must be used."""

    selections: tuple[RerankResult, ...] | None
    metadata: RankingMetadata


async def bounded_rerank(
    query: str,
    documents: list[str],
    reranker: RerankingRuntime | None,
    *,
    top_k: int,
    pre_degraded_reason: str | None = None,
) -> BoundedRerankingOutcome:
    """Rerank bounded candidates without making retrieval depend on the provider."""
    returned_count = min(top_k, len(documents))
    if reranker is None:
        return BoundedRerankingOutcome(
            selections=None,
            metadata=_metadata(
                state=RankingState.NOT_REQUESTED,
                comparable=False,
                reranker=None,
                reason=None,
                candidate_count=len(documents),
                returned_count=returned_count,
            ),
        )

    degraded_reason = pre_degraded_reason
    if (
        degraded_reason is None
        and len(documents) > reranker.adapter.capabilities.max_documents
    ):
        degraded_reason = "candidate_budget_exceeded"
    if (
        degraded_reason is None
        and sum(len(document) for document in documents) > MAX_RERANK_CHARACTERS
    ):
        degraded_reason = "candidate_content_budget_exceeded"

    if degraded_reason is None and documents:
        try:
            async with asyncio.timeout(RERANK_TIMEOUT_SECONDS):
                selections = await reranker.adapter.rerank(
                    query,
                    documents,
                    top_k=returned_count,
                )
            _validate_selections(
                selections,
                candidate_count=len(documents),
                expected_count=returned_count,
            )
        except RerankingError as error:
            degraded_reason = safe_degraded_reason(error.code)
        except TimeoutError:
            degraded_reason = "provider_timeout"
        else:
            return BoundedRerankingOutcome(
                selections=tuple(selections),
                metadata=_metadata(
                    state=RankingState.APPLIED,
                    comparable=True,
                    reranker=reranker,
                    reason=None,
                    candidate_count=len(documents),
                    returned_count=len(selections),
                ),
            )

    if not documents and degraded_reason is None:
        return BoundedRerankingOutcome(
            selections=(),
            metadata=_metadata(
                state=RankingState.APPLIED,
                comparable=True,
                reranker=reranker,
                reason="no_candidates",
                candidate_count=0,
                returned_count=0,
            ),
        )

    _log_degradation(reranker, degraded_reason)
    return BoundedRerankingOutcome(
        selections=None,
        metadata=_metadata(
            state=RankingState.DEGRADED,
            comparable=False,
            reranker=reranker,
            reason=degraded_reason,
            candidate_count=len(documents),
            returned_count=returned_count,
        ),
    )


def _validate_selections(
    selections: list[RerankResult],
    *,
    candidate_count: int,
    expected_count: int,
) -> None:
    indices = [selection.index for selection in selections]
    if (
        len(selections) != expected_count
        or len(indices) != len(set(indices))
        or any(index < 0 or index >= candidate_count for index in indices)
    ):
        raise RerankingError(
            "Reranking provider returned invalid selections.",
            code="invalid_response",
            retryable=True,
        )


def _metadata(
    *,
    state: RankingState,
    comparable: bool,
    reranker: RerankingRuntime | None,
    reason: str | None,
    candidate_count: int,
    returned_count: int,
) -> RankingMetadata:
    return RankingMetadata(
        state=state,
        comparable=comparable,
        reason=reason,
        provider=reranker.provider if reranker else None,
        provider_config_id=reranker.provider_config_id if reranker else None,
        provider_config_revision=(
            reranker.provider_config_revision if reranker else None
        ),
        candidate_count=candidate_count,
        returned_count=returned_count,
    )


def _log_degradation(
    reranker: RerankingRuntime,
    reason: str | None,
) -> None:
    logger.warning(
        "Reranking degraded provider=%s config_id=%s revision=%d reason=%s",
        reranker.provider,
        reranker.provider_config_id,
        reranker.provider_config_revision,
        reason,
    )


def safe_degraded_reason(code: str) -> str:
    return {
        "transport": "provider_unavailable",
        "rate_limited": "provider_rate_limited",
        "provider_unavailable": "provider_unavailable",
        "authentication": "provider_authentication_failed",
        "invalid_request": "provider_rejected_request",
        "invalid_response": "invalid_provider_response",
    }.get(code, "provider_unavailable")


__all__ = [
    "BoundedRerankingOutcome",
    "MAX_RERANK_CHARACTERS",
    "RERANK_TIMEOUT_SECONDS",
    "bounded_rerank",
    "safe_degraded_reason",
]
