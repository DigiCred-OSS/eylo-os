"""Cohere hosted or deployment-trusted compatible reranking."""

from __future__ import annotations

import httpx

from eylo.sockets.reranking.base import RerankingVendorAdapter
from eylo.sockets.reranking.schemas import (
    RerankResult,
    RerankingCapabilities,
    RerankingConfig,
    RerankingError,
)
from eylo.sockets.reranking.validation import (
    raise_for_status,
    validate_rerank_request,
    validate_rerank_results,
)

PROVIDER = "cohere"
API_URL = "https://api.cohere.com/v2/rerank"
MAX_DOCUMENTS = 1000
TIMEOUT_SECONDS = 10


class CohereRerankAdapter(RerankingVendorAdapter):
    def __init__(self, config: RerankingConfig) -> None:
        self._config = config

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> RerankingCapabilities:
        return RerankingCapabilities(max_documents=MAX_DOCUMENTS, truncates=True)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_k: int,
    ) -> list[RerankResult]:
        if not documents:
            return []
        expected_count = validate_rerank_request(
            query,
            documents,
            top_k=top_k,
            max_documents=MAX_DOCUMENTS,
            vendor=PROVIDER,
        )
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self._config.base_url or API_URL,
                    headers={"Authorization": f"Bearer {self._config.api_key}"},
                    json={
                        "model": self._config.model,
                        "query": query,
                        "documents": documents,
                        "top_n": expected_count,
                    },
                )
            raise_for_status(response, vendor=PROVIDER)
            payload = response.json()
            entries = payload.get("results") if isinstance(payload, dict) else None
            return validate_rerank_results(
                entries,
                expected_count=expected_count,
                candidate_count=len(documents),
                vendor=PROVIDER,
            )
        except RerankingError:
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            raise RerankingError(
                "Cohere reranking transport failed.",
                vendor=PROVIDER,
                code="transport",
                retryable=True,
            ) from None
        except (TypeError, ValueError):
            raise RerankingError(
                "Cohere returned invalid JSON.",
                vendor=PROVIDER,
                code="invalid_response",
                retryable=True,
            ) from None
