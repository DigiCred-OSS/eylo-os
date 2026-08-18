"""Block deletion while a published definition references a reranking config."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agents.models import AgentRevisionModel, AgentsModel
from eylo.modules.reranking_configs.wiring import build_reranking_config_service


class RerankingConfigReferenceLookup:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model in (AgentsModel, AgentRevisionModel):
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        model.reranking_provider_config_id == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class RerankingConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        async with start_transaction() as db:
            references = RerankingConfigReferenceLookup(db)
            await build_reranking_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
            )
