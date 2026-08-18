"""Atomic validation for untrusted reranking responses."""

from __future__ import annotations

import math
from numbers import Real

import httpx

from eylo.sockets.reranking.schemas import RerankResult, RerankingError


def raise_for_status(response: httpx.Response, *, vendor: str) -> None:
    if response.status_code < 400:
        return
    if response.status_code in {401, 403, 498}:
        code = "authentication"
        retryable = False
    elif response.status_code == 429:
        code = "rate_limited"
        retryable = True
    elif response.status_code >= 500:
        code = "provider_unavailable"
        retryable = True
    else:
        code = "invalid_request"
        retryable = False
    raise _error(
        "Reranking provider rejected the request.",
        vendor,
        code,
        retryable=retryable,
    )


def validate_rerank_request(
    query: str,
    documents: list[str],
    *,
    top_k: int,
    max_documents: int,
    vendor: str,
) -> int:
    if not isinstance(query, str) or not query.strip():
        raise _error("Reranking query must be non-empty.", vendor, "invalid_request")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise _error("top_k must be a positive integer.", vendor, "invalid_request")
    if len(documents) > max_documents:
        raise _error(
            "Reranking candidate limit exceeded.",
            vendor,
            "candidate_limit",
        )
    if any(not isinstance(document, str) or not document.strip() for document in documents):
        raise _error(
            "Reranking documents must be non-empty strings.",
            vendor,
            "invalid_request",
        )
    return min(top_k, len(documents))


def validate_rerank_results(
    entries: object,
    *,
    expected_count: int,
    candidate_count: int,
    vendor: str,
) -> list[RerankResult]:
    if not isinstance(entries, list) or len(entries) != expected_count:
        raise _invalid_response(vendor)

    results: list[RerankResult] = []
    seen: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise _invalid_response(vendor)
        index = entry.get("index")
        score = entry.get("relevance_score")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < candidate_count
            or index in seen
            or isinstance(score, bool)
            or not isinstance(score, Real)
            or not math.isfinite(float(score))
        ):
            raise _invalid_response(vendor)
        seen.add(index)
        results.append(RerankResult(index=index, score=float(score)))

    return sorted(results, key=lambda result: (-result.score, result.index))


def _invalid_response(vendor: str) -> RerankingError:
    return _error(
        "Reranking provider returned an invalid response.",
        vendor,
        "invalid_response",
        retryable=True,
    )


def _error(
    message: str,
    vendor: str,
    code: str,
    *,
    retryable: bool = False,
) -> RerankingError:
    return RerankingError(
        message,
        vendor=vendor,
        code=code,
        retryable=retryable,
    )
