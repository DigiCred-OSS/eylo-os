"""Bounded, revision-safe reranking provider verification."""

from __future__ import annotations

import asyncio
from uuid import UUID

from eylo.common.contracts.reranking import RerankingError
from eylo.common.database import start_transaction
from eylo.modules.reranking_configs.domain import RerankingProviderConfig
from eylo.modules.reranking_configs.verification import (
    RerankingProviderVerification,
    RerankingProviderVerifier,
    RerankingVerificationError,
    RerankingVerificationResult,
)
from eylo.modules.reranking_configs.wiring import build_reranking_config_service
from eylo.pipelines.reranking.config import build_reranking_runtime_config
from eylo.sockets.reranking.factory import RerankingFactory

_VERIFICATION_TIMEOUT_SECONDS = 10.0
_QUERY = "Which passage confirms the reranking provider is reachable?"
_DOCUMENTS = [
    "This passage confirms the reranking provider is reachable.",
    "This unrelated passage describes cloud formations.",
]


class RerankingRuntimeVerifier:
    """Run the same adapter and response validator used by live retrieval."""

    async def verify(
        self,
        config: RerankingProviderConfig,
    ) -> RerankingProviderVerification:
        adapter = RerankingFactory(
            config.provider.value,
            build_reranking_runtime_config(config),
        ).get_adapter()
        try:
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                results = await adapter.rerank(
                    _QUERY,
                    _DOCUMENTS,
                    top_k=len(_DOCUMENTS),
                )
        except RerankingError as error:
            raise RerankingVerificationError(
                f"Reranking provider verification failed ({error.code})."
            ) from None
        except Exception:
            raise RerankingVerificationError(
                "Reranking provider verification failed."
            ) from None
        if len(results) != len(_DOCUMENTS):
            raise RerankingVerificationError(
                "Reranking provider returned an incomplete result."
            )
        return RerankingProviderVerification(provider=config.provider.value)


class RerankingConfigVerificationUseCase:
    """Keep provider I/O outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: RerankingProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> RerankingVerificationResult:
        async with start_transaction():
            service = build_reranking_config_service()
            stored = await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = RerankingProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
                endpoint_policy=service.endpoint_policy,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_reranking_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
                verification_metadata={
                    "endpoint": provider_config.endpoint,
                    "model": provider_config.model,
                },
            )
        assert verified.verified_at is not None
        return RerankingVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
