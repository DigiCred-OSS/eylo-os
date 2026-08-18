"""Block deletion while sandbox authority remains in use."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.sandbox.models import (
    SandboxGrantModel,
    SandboxSessionModel,
    SandboxWorkspaceCheckpointModel,
)
from eylo.modules.sandbox_configs.wiring import build_sandbox_config_service


class SandboxConfigReferenceLookup:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model in (
            SandboxGrantModel,
            SandboxSessionModel,
            SandboxWorkspaceCheckpointModel,
        ):
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        model.sandbox_provider_config_id == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class SandboxConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        async with start_transaction() as db:
            references = SandboxConfigReferenceLookup(db)
            await build_sandbox_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
            )
