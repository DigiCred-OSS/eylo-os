"""Bounded, revision-safe verification of composed memory dependencies."""

from __future__ import annotations

import asyncio
from uuid import UUID

from eylo.common.contracts.memory import MemoryExtractionAuthority
from eylo.common.database import async_session_factory, start_transaction
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.memory.reindex_service import MemoryReindexService
from eylo.modules.memory_configs.catalog import MemoryProviders
from eylo.modules.memory_configs.domain import MemoryProviderConfig
from eylo.modules.memory_configs.verification import (
    MemoryDependencyAuthority,
    MemoryProviderVerifier,
    MemoryVerificationError,
    MemoryVerificationResult,
)
from eylo.modules.memory_configs.wiring import build_memory_config_service
from eylo.pipelines.embedding.resolver import resolve_embedding_runtime
from eylo.pipelines.memory.resolver import (
    build_memory_completer,
    memory_llm_overrides,
)
from eylo.sockets.memory.extraction import EXTRACTION_PROMPT_REVISION
from eylo.sockets.memory.vendors.pgvector import PgVectorMemoryAdapter

_VERIFICATION_TIMEOUT_SECONDS = 30.0


class MemoryRuntimeVerifier:
    """Run the same native dependencies and pgvector code used by live memory."""

    async def verify(
        self,
        *,
        organization_id: UUID,
        memory_config_id: UUID,
        memory_config_revision: int,
        config: MemoryProviderConfig,
        authority: MemoryDependencyAuthority,
        embedding_runtime,
        llm_runtime,
    ) -> None:
        if config.provider is not MemoryProviders.PGVECTOR:
            raise MemoryVerificationError("Unsupported memory provider.")
        space = embedding_runtime.space
        if (
            authority.embedding_provider_config_id != space.provider_config_id
            or authority.embedding_provider_config_revision
            != space.provider_config_revision
            or authority.embedding_space_id != space.id
            or authority.llm_provider_config_id != llm_runtime.provider_config_id
            or authority.llm_provider_config_revision
            != llm_runtime.provider_config_revision
            or authority.llm_provider != llm_runtime.provider.value
            or authority.llm_model != llm_runtime.generation.model.value
        ):
            raise MemoryVerificationError(
                "Memory dependency authority changed before verification."
            )
        adapter = PgVectorMemoryAdapter(
            async_session_factory,
            embedding_runtime.embed_documents,
            embedding_runtime.embed_query,
            build_memory_completer(llm_runtime),
            embedding_runtime.space,
            memory_provider_config_id=memory_config_id,
            memory_provider_config_revision=memory_config_revision,
            extraction_authority=MemoryExtractionAuthority(
                provider_config_id=llm_runtime.provider_config_id,
                provider_config_revision=llm_runtime.provider_config_revision,
                provider=llm_runtime.provider.value,
                model=llm_runtime.generation.model.value,
                prompt_revision=EXTRACTION_PROMPT_REVISION,
            ),
        )
        try:
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                await adapter.verify()
        except Exception:
            raise MemoryVerificationError(
                "Memory provider verification failed."
            ) from None


class MemoryConfigVerificationUseCase:
    """Resolve dependencies outside DB transactions, then CAS memory revision."""

    def __init__(self, verifier: MemoryProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> MemoryVerificationResult:
        async with start_transaction():
            stored = await build_memory_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
            config = MemoryProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        async with start_transaction() as db:
            embedding = await resolve_embedding_runtime(
                organization_id,
                provider_config_id=config.embedding_provider_config_id,
                db=db,
            )
            llm = await build_llm_config_resolver(db).resolve_llm(
                organization_id,
                provider_config_id=config.llm_provider_config_id,
                overrides=memory_llm_overrides(),
            )
        authority = MemoryDependencyAuthority(
            embedding_provider_config_id=embedding.space.provider_config_id,
            embedding_provider_config_revision=(
                embedding.space.provider_config_revision
            ),
            embedding_provider=embedding.space.provider,
            embedding_endpoint=embedding.space.endpoint,
            embedding_model=embedding.space.model,
            embedding_dimensions=embedding.space.dimensions,
            embedding_semantic_options=dict(embedding.space.semantic_options),
            embedding_space_id=embedding.space.id,
            llm_provider_config_id=llm.provider_config_id,
            llm_provider_config_revision=llm.provider_config_revision,
            llm_provider=llm.provider.value,
            llm_model=llm.generation.model.value,
        )
        if (
            authority.embedding_provider_config_id
            != config.embedding_provider_config_id
            or authority.llm_provider_config_id != config.llm_provider_config_id
        ):
            raise MemoryVerificationError(
                "Memory dependency identity changed during verification."
            )

        await self._verifier.verify(
            organization_id=organization_id,
            memory_config_id=config_id,
            memory_config_revision=expected_revision,
            config=config,
            authority=authority,
            embedding_runtime=embedding,
            llm_runtime=llm,
        )

        async with start_transaction() as db:
            verified = await build_memory_config_service(db).mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
                verification_metadata=authority.to_metadata(),
            )
            await MemoryReindexService(db).record_verified_space(
                organization_id=organization_id,
                memory_provider_config_id=config_id,
                verified_space=embedding.space,
            )
        assert verified.verified_at is not None
        return MemoryVerificationResult(
            provider=verified.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
