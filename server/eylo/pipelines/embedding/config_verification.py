"""Bounded, revision-safe embedding provider verification."""

from __future__ import annotations

import asyncio
from uuid import UUID

from eylo.common.contracts.embedding import EmbeddingError, EmbeddingInput
from eylo.common.database import start_transaction
from eylo.modules.embedding_configs.domain import EmbeddingProviderConfig
from eylo.modules.embedding_configs.verification import (
    EmbeddingProviderVerification,
    EmbeddingProviderVerifier,
    EmbeddingVerificationError,
    EmbeddingVerificationResult,
)
from eylo.modules.embedding_configs.wiring import build_embedding_config_service
from eylo.pipelines.embedding.config import build_embedding_runtime_config
from eylo.sockets.embedding.factory import EmbeddingFactory

_VERIFICATION_TIMEOUT_SECONDS = 60.0
_SENTINEL = "eylo embedding capability verification"


class EmbeddingRuntimeVerifier:
    """Run both retrieval intents through the same adapter used at runtime."""

    async def verify(
        self,
        config: EmbeddingProviderConfig,
    ) -> EmbeddingProviderVerification:
        adapter = EmbeddingFactory(
            config.provider.value,
            build_embedding_runtime_config(config),
        ).get_adapter()
        try:
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                documents = await adapter.embed(
                    [_SENTINEL],
                    input_type=EmbeddingInput.DOCUMENT,
                )
                queries = await adapter.embed(
                    [_SENTINEL],
                    input_type=EmbeddingInput.QUERY,
                )
        except EmbeddingError as error:
            raise EmbeddingVerificationError(
                f"Embedding provider verification failed ({error.code})."
            ) from None
        except Exception:
            raise EmbeddingVerificationError(
                "Embedding provider verification failed."
            ) from None
        dimensions = {len(vector) for vector in (*documents, *queries)}
        if len(documents) != 1 or len(queries) != 1 or len(dimensions) != 1:
            raise EmbeddingVerificationError(
                "Embedding provider returned an unstable vector shape."
            )
        dimension = dimensions.pop()
        if dimension < 1:
            raise EmbeddingVerificationError(
                "Embedding provider returned an empty vector."
            )
        return EmbeddingProviderVerification(
            provider=config.provider.value,
            dimensions=dimension,
        )


class EmbeddingConfigVerificationUseCase:
    """Keep provider I/O outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: EmbeddingProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> EmbeddingVerificationResult:
        async with start_transaction():
            service = build_embedding_config_service()
            stored = await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = EmbeddingProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
                endpoint_policy=service.endpoint_policy,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_embedding_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
                verification_metadata={
                    "dimensions": result.dimensions,
                    "endpoint": provider_config.endpoint,
                    "model": provider_config.model,
                },
            )
        assert verified.verified_at is not None
        return EmbeddingVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            dimensions=result.dimensions,
            verified_at=verified.verified_at,
        )
