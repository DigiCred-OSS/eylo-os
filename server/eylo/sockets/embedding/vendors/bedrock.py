"""AWS Bedrock Runtime adapter for Titan Text Embeddings V2."""

from __future__ import annotations

import json

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from eylo.sockets.embedding.base import EmbeddingVendorAdapter
from eylo.sockets.embedding.schemas import (
    BedrockEmbeddingConfig,
    EmbeddingCapabilities,
    EmbeddingError,
    EmbeddingInput,
    EmbeddingSemanticOptions,
)
from eylo.sockets.embedding.validation import validate_indexed_vectors

PROVIDER = "bedrock"
MAX_BATCH = 1


class BedrockEmbeddingAdapter(EmbeddingVendorAdapter):
    """Invoke one explicit Titan V2 model through AWS Bedrock Runtime."""

    def __init__(self, config: BedrockEmbeddingConfig) -> None:
        self._config = config
        self._session = aioboto3.Session(
            aws_access_key_id=config.access_key_id.get_secret_value(),
            aws_secret_access_key=config.secret_access_key.get_secret_value(),
            aws_session_token=(
                config.session_token.get_secret_value()
                if config.session_token is not None
                else None
            ),
            region_name=config.region,
        )

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> EmbeddingCapabilities:
        return EmbeddingCapabilities(
            asymmetric=False,
            max_batch=MAX_BATCH,
            dimensions=self._config.dimensions,
        )

    @property
    def semantic_options(self) -> EmbeddingSemanticOptions:
        return {
            "protocol_revision": 1,
            "input_mode": "symmetric",
            "normalize": self._config.normalize,
        }

    async def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInput = EmbeddingInput.DOCUMENT,
    ) -> list[list[float]]:
        del input_type  # Titan V2 uses one symmetric request shape for both intents.
        if not texts:
            return []

        try:
            vectors: list[list[float]] = []
            async with self._session.client("bedrock-runtime") as client:
                for text in texts:
                    response = await client.invoke_model(
                        modelId=self._config.model,
                        contentType="application/json",
                        accept="application/json",
                        body=json.dumps(
                            {
                                "inputText": text,
                                "dimensions": self._config.dimensions,
                                "normalize": self._config.normalize,
                            }
                        ),
                    )
                    body = response.get("body")
                    if body is None:
                        raise _invalid_response("Bedrock response body is missing.")
                    payload = json.loads(await body.read())
                    embedding = payload.get("embedding") if isinstance(payload, dict) else None
                    vector = validate_indexed_vectors(
                        [(0, embedding)],
                        expected_count=1,
                        vendor=PROVIDER,
                    )[0]
                    if len(vector) != self._config.dimensions:
                        raise _invalid_response(
                            "Bedrock returned a vector with unexpected dimensions."
                        )
                    vectors.append(vector)
            return vectors
        except EmbeddingError:
            raise
        except ClientError as error:
            raise _client_error(error) from None
        except BotoCoreError:
            raise EmbeddingError(
                "Bedrock embedding transport failed.",
                vendor=PROVIDER,
                code="transport",
                retryable=True,
            ) from None
        except (AttributeError, json.JSONDecodeError, TypeError, ValueError):
            raise _invalid_response("Bedrock returned an invalid response.") from None


def _client_error(error: ClientError) -> EmbeddingError:
    provider_code = str(error.response.get("Error", {}).get("Code", ""))
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    if provider_code in {
        "AccessDeniedException",
        "ExpiredTokenException",
        "InvalidSignatureException",
        "UnrecognizedClientException",
    } or status in {401, 403}:
        code = "authentication"
        retryable = False
    elif provider_code in {"ThrottlingException", "ServiceQuotaExceededException"}:
        code = "rate_limited"
        retryable = True
    elif provider_code in {
        "InternalServerException",
        "ModelNotReadyException",
        "ModelTimeoutException",
        "ServiceUnavailableException",
    } or (isinstance(status, int) and status >= 500):
        code = "provider_error"
        retryable = True
    else:
        code = "invalid_request"
        retryable = False
    return EmbeddingError(
        "Bedrock rejected the embedding request.",
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
