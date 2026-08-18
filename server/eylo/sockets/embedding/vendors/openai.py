"""OpenAI and operator-trusted OpenAI-compatible embeddings."""

from __future__ import annotations

from eylo.sockets.embedding.base import EmbeddingVendorAdapter
from eylo.sockets.embedding.schemas import (
    EmbeddingCapabilities,
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingInput,
    EmbeddingSemanticOptions,
)
from eylo.sockets.embedding.validation import validate_indexed_vectors

PROVIDER = "openai"
MAX_BATCH = 256


class OpenAIEmbeddingAdapter(EmbeddingVendorAdapter):
    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> EmbeddingCapabilities:
        return EmbeddingCapabilities(
            asymmetric=False,
            max_batch=MAX_BATCH,
            dimensions=None,
        )

    @property
    def semantic_options(self) -> EmbeddingSemanticOptions:
        return {"protocol_revision": 1, "input_mode": "symmetric"}

    async def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInput = EmbeddingInput.DOCUMENT,
    ) -> list[list[float]]:
        if not texts:
            return []

        from openai import AsyncOpenAI

        try:
            async with AsyncOpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url or None,
            ) as client:
                vectors: list[list[float]] = []
                for start in range(0, len(texts), MAX_BATCH):
                    batch = texts[start : start + MAX_BATCH]
                    response = await client.embeddings.create(
                        model=self._config.model,
                        input=batch,
                    )
                    vectors.extend(
                        validate_indexed_vectors(
                            [
                                (item.index, item.embedding)
                                for item in response.data
                            ],
                            expected_count=len(batch),
                            vendor=PROVIDER,
                        )
                    )
                return vectors
        except EmbeddingError:
            raise
        except Exception as error:
            raise _normalized_openai_error(error) from None


def _normalized_openai_error(error: Exception) -> EmbeddingError:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    if isinstance(error, AuthenticationError):
        return EmbeddingError(
            "OpenAI embedding authentication failed.",
            vendor=PROVIDER,
            code="authentication",
        )
    if isinstance(error, BadRequestError):
        return EmbeddingError(
            "OpenAI rejected the embedding request.",
            vendor=PROVIDER,
            code="invalid_request",
        )
    if isinstance(error, RateLimitError):
        return EmbeddingError(
            "OpenAI rate-limited the embedding request.",
            vendor=PROVIDER,
            code="rate_limited",
            retryable=True,
        )
    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return EmbeddingError(
            "OpenAI embedding transport failed.",
            vendor=PROVIDER,
            code="transport",
            retryable=True,
        )
    if isinstance(error, APIStatusError):
        return EmbeddingError(
            "OpenAI embedding provider failed.",
            vendor=PROVIDER,
            code="provider_error",
            retryable=error.status_code >= 500,
        )
    return EmbeddingError(
        "OpenAI embedding request failed.",
        vendor=PROVIDER,
        code="provider_error",
    )
