"""Operator composition for requesting durable knowledgebase reindex work."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from eylo.absurd_work import AbsurdBoundWorkService
from eylo.common.contracts.embedding import (
    EmbeddingSpace,
    embedding_space_from_record,
    target_embedding_space_from_record,
)
from eylo.common.database import start_transaction
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.knowledgebase.jobs import KnowledgeReindexJobModel
from eylo.modules.knowledgebase.models import KnowledgebaseModel
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.modules.knowledgebase.services.reindex import KnowledgeReindexService
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.resolver import resolve_embedding_runtime
from eylo.pipelines.knowledgebase.reindex_durable_execution import (
    spawn_knowledge_reindex,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class KnowledgeReindexInspection:
    knowledgebase: KnowledgebaseModel
    active_space: EmbeddingSpace
    target_space: EmbeddingSpace | None
    available_space: EmbeddingSpace | None
    latest_job: KnowledgeReindexJobModel | None


async def inspect_knowledgebase_reindex(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
) -> KnowledgeReindexInspection:
    async with start_transaction(ro=True) as session:
        knowledgebase = await KnowledgebaseService(session).get(
            knowledgebase_id,
            organization_id,
        )
        if knowledgebase.vendor != "pgvector":
            raise KnowledgebaseError(
                "Only pgvector knowledgebases have an embedding index."
            )
        active_space = embedding_space_from_record(knowledgebase)
        if active_space is None:
            raise KnowledgebaseError(
                "Knowledgebase has no active embedding authority."
            )
        available_space = None
        if knowledgebase.embedding_provider_config_id is not None:
            try:
                runtime = await resolve_embedding_runtime(
                    organization_id,
                    provider_config_id=knowledgebase.embedding_provider_config_id,
                    db=session,
                )
                available_space = runtime.space
            except (
                InvalidEmbeddingConfig,
                NotConfiguredError,
                SecretCipherError,
            ):
                pass
        latest_job = await KnowledgeReindexService(session).latest_job(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
        )
        return KnowledgeReindexInspection(
            knowledgebase=knowledgebase,
            active_space=active_space,
            target_space=target_embedding_space_from_record(knowledgebase),
            available_space=available_space,
            latest_job=latest_job,
        )


async def request_knowledgebase_reindex(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
    embedding_provider_config_id: UUID,
) -> KnowledgeReindexJobModel:
    """Commit product intent first; a lost spawn is recovered from PostgreSQL."""
    async with start_transaction() as session:
        runtime = await resolve_embedding_runtime(
            organization_id,
            provider_config_id=embedding_provider_config_id,
            db=session,
        )
        job = await KnowledgeReindexService(session).request(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            target_space=runtime.space,
        )
        job_id = UUID(str(job.id))

    try:
        await spawn_knowledge_reindex(
            organization_id=organization_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001 - committed DB row is the outbox
        logger.error(
            "Knowledge reindex spawn deferred id=%s error_type=%s",
            job_id,
            type(error).__name__,
        )

    async with start_transaction(ro=True) as session:
        return await AbsurdBoundWorkService(
            KnowledgeReindexJobModel,
            session,
        ).get(work_id=job_id, organization_id=organization_id)
