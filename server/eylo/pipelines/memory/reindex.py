"""Operator composition for requesting durable Memory reindex work."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from eylo.common.contracts.embedding import (
    EmbeddingSpace,
    embedding_space_from_record,
    target_embedding_space_from_record,
)
from eylo.common.database import start_transaction
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.memory.models import (
    MemoryIndexModel,
    MemoryReindexJobModel,
)
from eylo.modules.memory.reindex_service import MemoryReindexService
from eylo.modules.memory_configs.domain import (
    InvalidMemoryConfig,
    MemoryProviderConfig,
)
from eylo.modules.memory_configs.wiring import build_memory_config_service
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.provider_configs.domain import ProviderConfigNotFound
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.resolver import resolve_embedding_runtime
from eylo.pipelines.memory.reindex_durable_execution import spawn_memory_reindex

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MemoryReindexInspection:
    index: MemoryIndexModel | None
    active_space: EmbeddingSpace | None
    target_space: EmbeddingSpace | None
    available_space: EmbeddingSpace | None
    latest_job: MemoryReindexJobModel | None


async def inspect_memory_reindex(
    *,
    organization_id: UUID,
    memory_provider_config_id: UUID,
) -> MemoryReindexInspection:
    async with start_transaction(ro=True) as session:
        config_service = build_memory_config_service(session)
        try:
            stored = await config_service.get(
                organization_id=organization_id,
                config_id=memory_provider_config_id,
            )
        except SecretCipherError:
            configs = await config_service.list(organization_id=organization_id)
            stored = next(
                (
                    config
                    for config in configs
                    if str(config.id) == str(memory_provider_config_id)
                ),
                None,
            )
            if stored is None:
                raise ProviderConfigNotFound(
                    "Provider configuration was not found."
                ) from None

        available_space = None
        try:
            config = MemoryProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            runtime = await resolve_embedding_runtime(
                organization_id,
                provider_config_id=config.embedding_provider_config_id,
                db=session,
            )
            available_space = runtime.space
        except (
            InvalidEmbeddingConfig,
            InvalidMemoryConfig,
            NotConfiguredError,
            SecretCipherError,
        ):
            pass

        service = MemoryReindexService(session)
        index = await service.index(
            organization_id=organization_id,
            memory_provider_config_id=memory_provider_config_id,
        )
        return MemoryReindexInspection(
            index=index,
            active_space=(
                None if index is None else embedding_space_from_record(index)
            ),
            target_space=(
                None if index is None else target_embedding_space_from_record(index)
            ),
            available_space=available_space,
            latest_job=await service.latest_job(
                organization_id=organization_id,
                memory_provider_config_id=memory_provider_config_id,
            ),
        )


async def request_memory_reindex(
    *,
    organization_id: UUID,
    memory_provider_config_id: UUID,
) -> MemoryReindexJobModel:
    """Commit product intent first; a lost spawn is recovered from PostgreSQL."""
    async with start_transaction() as session:
        stored = await build_memory_config_service(session).get(
            organization_id=organization_id,
            config_id=memory_provider_config_id,
        )
        config = MemoryProviderConfig.validate(
            provider=stored.provider,
            config=stored.config,
            secrets=stored.secrets,
        )
        runtime = await resolve_embedding_runtime(
            organization_id,
            provider_config_id=config.embedding_provider_config_id,
            db=session,
        )
        service = MemoryReindexService(session)
        await service.record_verified_space(
            organization_id=organization_id,
            memory_provider_config_id=memory_provider_config_id,
            verified_space=runtime.space,
        )
        job = await service.request(
            organization_id=organization_id,
            memory_provider_config_id=memory_provider_config_id,
        )
        job_id = UUID(str(job.id))

    try:
        await spawn_memory_reindex(
            organization_id=organization_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001 - committed DB row is the outbox
        logger.error(
            "Memory reindex spawn deferred id=%s error_type=%s",
            job_id,
            type(error).__name__,
        )

    async with start_transaction(ro=True) as session:
        return await MemoryReindexService(session).get_job(
            organization_id=organization_id,
            job_id=job_id,
        )
