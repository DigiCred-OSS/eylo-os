"""Runtime configs plus vendor-neutral reranking exports."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from eylo.common.contracts import reranking as reranking_contracts

RerankResult = reranking_contracts.RerankResult
RerankingCapabilities = reranking_contracts.RerankingCapabilities
RerankingConfig = reranking_contracts.RerankingConfig
RerankingError = reranking_contracts.RerankingError


class BedrockRerankingConfig(BaseModel):
    """Explicit AWS Bedrock Agent Runtime reranking configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    model: Literal["amazon.rerank-v1:0", "cohere.rerank-v3-5:0"]
    region: str = Field(
        min_length=5,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)+$",
    )
    access_key_id: SecretStr = Field(min_length=1, max_length=512)
    secret_access_key: SecretStr = Field(min_length=1, max_length=8192)
    session_token: SecretStr | None = Field(default=None, max_length=8192)


RerankingRuntimeConfig = RerankingConfig | BedrockRerankingConfig
