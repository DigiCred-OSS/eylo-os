"""Runtime configs plus vendor-neutral embedding exports."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr

from eylo.common.contracts import embedding as embedding_contracts

EmbeddingCapabilities = embedding_contracts.EmbeddingCapabilities
EmbeddingConfig = embedding_contracts.EmbeddingConfig
EmbeddingError = embedding_contracts.EmbeddingError
EmbeddingInput = embedding_contracts.EmbeddingInput
EmbeddingSemanticOptions = dict[str, JsonValue]


class BedrockEmbeddingConfig(BaseModel):
    """Explicit AWS Bedrock Runtime configuration for Titan Text Embeddings V2."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    model: Literal["amazon.titan-embed-text-v2:0"]
    region: str = Field(
        min_length=5,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)+$",
    )
    dimensions: Literal[256, 512, 1024]
    normalize: bool
    access_key_id: SecretStr = Field(min_length=1, max_length=512)
    secret_access_key: SecretStr = Field(min_length=1, max_length=8192)
    session_token: SecretStr | None = Field(default=None, max_length=8192)


EmbeddingRuntimeConfig = EmbeddingConfig | BedrockEmbeddingConfig
