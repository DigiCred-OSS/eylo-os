"""AWS Bedrock Agent Runtime reranking adapter."""

from __future__ import annotations

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from eylo.sockets.reranking.base import RerankingVendorAdapter
from eylo.sockets.reranking.schemas import (
    BedrockRerankingConfig,
    RerankResult,
    RerankingCapabilities,
    RerankingError,
)
from eylo.sockets.reranking.validation import (
    validate_rerank_request,
    validate_rerank_results,
)

PROVIDER = "bedrock"
MAX_DOCUMENTS = 1000


class BedrockRerankAdapter(RerankingVendorAdapter):
    """Rerank inline text through one explicitly selected Bedrock model."""

    def __init__(self, config: BedrockRerankingConfig) -> None:
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
        request = {
            "queries": [{"type": "TEXT", "textQuery": {"text": query}}],
            "sources": [
                {
                    "type": "INLINE",
                    "inlineDocumentSource": {
                        "type": "TEXT",
                        "textDocument": {"text": document},
                    },
                }
                for document in documents
            ],
            "rerankingConfiguration": {
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "numberOfResults": expected_count,
                    "modelConfiguration": {"modelArn": self._model_arn},
                },
            },
        }
        try:
            entries: list[dict[str, object]] = []
            next_token: str | None = None
            seen_tokens: set[str] = set()
            async with self._session.client("bedrock-agent-runtime") as client:
                while True:
                    response = await client.rerank(
                        **request,
                        **({"nextToken": next_token} if next_token else {}),
                    )
                    page = response.get("results")
                    if not isinstance(page, list):
                        raise _invalid_response()
                    entries.extend(
                        {
                            "index": item.get("index"),
                            "relevance_score": item.get("relevanceScore"),
                        }
                        for item in page
                        if isinstance(item, dict)
                    )
                    raw_next_token = response.get("nextToken")
                    if raw_next_token is None:
                        break
                    if (
                        not isinstance(raw_next_token, str)
                        or not raw_next_token
                        or raw_next_token in seen_tokens
                    ):
                        raise _invalid_response()
                    seen_tokens.add(raw_next_token)
                    next_token = raw_next_token
            return validate_rerank_results(
                entries,
                expected_count=expected_count,
                candidate_count=len(documents),
                vendor=PROVIDER,
            )
        except RerankingError:
            raise
        except ClientError as error:
            raise _client_error(error) from None
        except BotoCoreError:
            raise RerankingError(
                "Bedrock reranking transport failed.",
                vendor=PROVIDER,
                code="transport",
                retryable=True,
            ) from None

    @property
    def _model_arn(self) -> str:
        return (
            f"arn:aws:bedrock:{self._config.region}::foundation-model/"
            f"{self._config.model}"
        )


def _client_error(error: ClientError) -> RerankingError:
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
        "ServiceUnavailableException",
    } or (isinstance(status, int) and status >= 500):
        code = "provider_unavailable"
        retryable = True
    else:
        code = "invalid_request"
        retryable = False
    return RerankingError(
        "Bedrock rejected the reranking request.",
        vendor=PROVIDER,
        code=code,
        retryable=retryable,
    )


def _invalid_response() -> RerankingError:
    return RerankingError(
        "Bedrock returned an invalid reranking response.",
        vendor=PROVIDER,
        code="invalid_response",
        retryable=True,
    )
