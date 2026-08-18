"""Block deletion while durable vector authority references a config."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agents.models import AgentRevisionModel, AgentsModel
from eylo.modules.embedding_configs.wiring import build_embedding_config_service
from eylo.modules.knowledgebase.jobs import (
    KnowledgeIngestionJobModel,
    KnowledgeReindexJobModel,
)
from eylo.modules.knowledgebase.models import KnowledgebaseModel
from eylo.modules.memory.models import (
    MemoryChangeModel,
    MemoryFormationJobModel,
    MemoryIndexModel,
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationJobModel,
    MemoryReindexJobModel,
)
from eylo.modules.provider_configs.constants import Capability
from eylo.pipelines.memory.dependency_references import (
    CombinedProviderConfigReferences,
    MemoryDependencyReferenceLookup,
)


class EmbeddingConfigReferenceLookup:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model in (
            AgentsModel,
            AgentRevisionModel,
            KnowledgebaseModel,
            KnowledgeIngestionJobModel,
            MemoryModel,
            MemoryChangeModel,
            MemoryFormationJobModel,
            MemoryReconciliationJobModel,
            MemoryReconciliationCursorModel,
            MemoryIndexModel,
        ):
            config_column = (
                model.file_upload_embedding_provider_config_id
                if model in (AgentsModel, AgentRevisionModel)
                else model.embedding_provider_config_id
            )
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        config_column == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        additional_references = (
            (KnowledgebaseModel, KnowledgebaseModel.target_embedding_provider_config_id),
            (MemoryIndexModel, MemoryIndexModel.target_embedding_provider_config_id),
            (
                KnowledgeReindexJobModel,
                KnowledgeReindexJobModel.source_embedding_provider_config_id,
            ),
            (
                KnowledgeReindexJobModel,
                KnowledgeReindexJobModel.target_embedding_provider_config_id,
            ),
            (
                MemoryReindexJobModel,
                MemoryReindexJobModel.source_embedding_provider_config_id,
            ),
            (
                MemoryReindexJobModel,
                MemoryReindexJobModel.target_embedding_provider_config_id,
            ),
        )
        for model, config_column in additional_references:
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        config_column == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class EmbeddingConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        async with start_transaction() as db:
            references = CombinedProviderConfigReferences(
                EmbeddingConfigReferenceLookup(db),
                MemoryDependencyReferenceLookup(db, Capability.EMBEDDING),
            )
            await build_embedding_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
            )
