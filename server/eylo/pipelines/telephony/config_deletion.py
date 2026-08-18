"""Block deletion while a carrier config remains authoritative."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.telephony.models import PhoneNumberModel, TelephonyCallModel
from eylo.modules.telephony.wiring import build_telephony_config_service


class TelephonyConfigReferenceLookup:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model in (PhoneNumberModel, TelephonyCallModel):
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        model.provider_config_id == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class TelephonyConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        async with start_transaction() as db:
            references = TelephonyConfigReferenceLookup(db)
            await build_telephony_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
            )
