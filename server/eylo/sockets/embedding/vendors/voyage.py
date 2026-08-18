"""Voyage embeddings with explicit query/document intent."""

from __future__ import annotations

import httpx

from eylo.sockets.embedding.base import EmbeddingVendorAdapter
from eylo.sockets.embedding.schemas import (
    EmbeddingCapabilities,
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingInput,
    EmbeddingSemanticOptions,
)
from eylo.sockets.embedding.validation import validate_indexed_vectors

PROVIDER = "voyage"
API_URL = "https://api.voyageai.com/v1/embeddings"
MAX_BATCH = 128
TIMEOUT_SECONDS = 60


class VoyageEmbeddingAdapter(EmbeddingVendorAdapter):
    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> EmbeddingCapabilities:
        return EmbeddingCapabilities(
            asymmetric=True,
            max_batch=MAX_BATCH,
            dimensions=None,
        )

    @property
    def semantic_options(self) -> EmbeddingSemanticOptions:
        return {
            "protocol_revision": 1,
            "document_input_type": EmbeddingInput.DOCUMENT.value,
            "query_input_type": EmbeddingInput.QUERY.value,
            "truncation": False,
            "output_dtype": "float",
        }

    async def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInput = EmbeddingInput.DOCUMENT,
    ) -> list[list[float]]:
        if not texts:
            return []

        try:
            vectors: list[list[float]] = []
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                for start in range(0, len(texts), MAX_BATCH):
                    batch = texts[start : start + MAX_BATCH]
                    response = await client.post(
                        API_URL,
                        headers={"Authorization": f"Bearer {self._config.api_key}"},
                        json={
                            "model": self._config.model,
                            "input": batch,
                            "input_type": input_type.value,
                            "truncation": False,
                            "output_dtype": "float",
                        },
                    )
                    _raise_for_status(response)
                    payload = response.json()
                    data = payload.get("data") if isinstance(payload, dict) else None
                    if not isinstance(data, list):
                        raise _invalid_response("Voyage response data is missing.")
                    vectors.extend(
                        validate_indexed_vectors(
                            [
                                (item.get("index"), item.get("embedding"))
                                for item in data
                                if isinstance(item, dict)
                            ],
                            expected_count=len(batch),
                            vendor=PROVIDER,
                        )
                    )
            return vectors
        except EmbeddingError:
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            raise EmbeddingError(
                "Voyage embedding transport failed.",
                vendor=PROVIDER,
                code="transport",
                retryable=True,
            ) from None
        except (TypeError, ValueError):
            raise _invalid_response("Voyage returned invalid JSON.") from None


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    if response.status_code in {401, 403}:
        code = "authentication"
        retryable = False
    elif response.status_code == 429:
        code = "rate_limited"
        retryable = True
    elif response.status_code >= 500:
        code = "provider_error"
        retryable = True
    else:
        code = "invalid_request"
        retryable = False
    raise EmbeddingError(
        "Voyage rejected the embedding request.",
        vendor=PROVIDER,
        code=code,
        retryable=retryable,
    )


def _invalid_response(message: str) -> EmbeddingError:
    return EmbeddingError(
        message,
        vendor=PROVIDER,
        code="invalid_response",
        retryable=True,
    )
