"""Block deletion while memory authority is still referenced."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agents.models import AgentRevisionModel, AgentsModel
from eylo.modules.memory.models import (
    MemoryChangeModel,
    MemoryFormationCursorModel,
    MemoryFormationJobModel,
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationJobModel,
    MemoryReindexJobModel,
    MemoryRelationshipModel,
)
from eylo.modules.memory_configs.wiring import build_memory_config_service


class MemoryConfigReferenceLookup:
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
            MemoryModel,
            MemoryChangeModel,
            MemoryFormationJobModel,
            MemoryFormationCursorModel,
            MemoryReconciliationJobModel,
            MemoryReconciliationCursorModel,
            MemoryRelationshipModel,
            MemoryReindexJobModel,
        ):
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        model.memory_provider_config_id == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class MemoryConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        async with start_transaction() as db:
            references = MemoryConfigReferenceLookup(db)
            await build_memory_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
            )
