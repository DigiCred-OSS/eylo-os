"""Repository for telephony database operations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from eylo.common.repositories import BaseORMRepository
from eylo.modules.telephony.models import (
    PhoneNumberModel,
    TelephonyCallModel,
)
from eylo.modules.telephony.schemas import (
    PhoneNumberCreateSchema,
    PhoneNumberStatus,
    PhoneNumberUpdateSchema,
)


class PhoneNumberRepository(BaseORMRepository[PhoneNumberModel]):
    @property
    def model(self) -> type[PhoneNumberModel]:
        return PhoneNumberModel

    async def create(
        self, organization_id: UUID, request: PhoneNumberCreateSchema
    ) -> PhoneNumberModel:
        phone_number = self.model(
            organization_id=organization_id,
            **request.model_dump(),
        )
        return await self.save_(phone_number)

    async def prepare_provisioning(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
        number: str,
        label: str | None,
        provider: str,
        provider_config_id: UUID,
        provider_config_revision: int,
    ) -> PhoneNumberModel | None:
        """Insert one stable purchase intent without racing provider I/O."""
        statement = (
            insert(self.model)
            .values(
                id=phone_number_id,
                organization_id=organization_id,
                number=number,
                label=label,
                status=PhoneNumberStatus.PROVISIONING,
                provider=provider,
                provider_config_id=provider_config_id,
                provider_config_revision=provider_config_revision,
            )
            .on_conflict_do_nothing()
            .returning(self.model.id)
        )
        await self.db_session.execute(statement)
        return await self.get_by_id_in_organization(
            phone_number_id=phone_number_id,
            organization_id=organization_id,
        )

    async def get_by_id_in_organization(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
        for_update: bool = False,
    ) -> PhoneNumberModel | None:
        query = select(self.model).where(
            self.model.id == phone_number_id,
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self, phone_number_id: UUID, request: PhoneNumberUpdateSchema
    ) -> PhoneNumberModel:
        phone_number = await self.get_(phone_number_id)
        if not phone_number:
            raise ValueError("Phone number not found")

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(phone_number, key, value)

        return await self.partial_update_(entity=phone_number)

    async def soft_delete(self, phone_number_id: UUID) -> PhoneNumberModel:
        phone_number = await self.get_(phone_number_id)
        if not phone_number:
            raise ValueError("Phone number not found")
        phone_number.deleted = True
        return await self.partial_update_(phone_number)

    async def get_active_by_outbound_agent_id(
        self,
        *,
        organization_id: UUID,
        outbound_agent_id: UUID,
    ) -> PhoneNumberModel | None:
        """Resolve one routable number; inactive/deleted rows never authorize work."""
        query = select(self.model).where(
            self.model.organization_id == organization_id,
            self.model.outbound_agent_id == outbound_agent_id,
            self.model.status == "ACTIVE",
            self.model.deleted.is_(False),
        )
        result = await self.db_session.execute(query.limit(2))
        rows = list(result.scalars())
        if len(rows) > 1:
            raise ValueError("Agent has ambiguous active outbound phone routing.")
        return rows[0] if rows else None


class TelephonyCallRepository(BaseORMRepository[TelephonyCallModel]):
    @property
    def model(self) -> type[TelephonyCallModel]:
        return TelephonyCallModel

    async def get_by_call_sid(
        self,
        call_sid: str,
        organization_id: UUID | None = None,
    ) -> Optional[TelephonyCallModel]:
        filters = [
            self.model.call_sid == call_sid,
            self.model.deleted.is_(False),
        ]
        if organization_id is not None:
            filters.append(self.model.organization_id == organization_id)
        results = await self.filter_(filters=filters, limit=1)
        return results[0] if results else None

    async def get_by_call_sid_for_update(
        self,
        call_sid: str,
        organization_id: UUID | None = None,
    ) -> Optional[TelephonyCallModel]:
        query = select(self.model).where(
            self.model.call_sid == call_sid,
            self.model.deleted.is_(False),
        )
        if organization_id is not None:
            query = query.where(self.model.organization_id == organization_id)
        result = await self.db_session.execute(query.limit(1).with_for_update())
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
    ) -> List[TelephonyCallModel]:
        filters = [self.model.organization_id == organization_id]
        if status:
            filters.append(self.model.status == status)
        if direction:
            filters.append(self.model.direction == direction)
        if campaign_id:
            filters.append(self.model.campaign_id == campaign_id)
        if conversation_id:
            filters.append(self.model.conversation_id == conversation_id)
        return await self.filter_(
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=[self.model.created_at.desc()],
        )

    async def count_by_organization(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
    ) -> int:
        filters = [self.model.organization_id == organization_id]
        if status:
            filters.append(self.model.status == status)
        if direction:
            filters.append(self.model.direction == direction)
        if campaign_id:
            filters.append(self.model.campaign_id == campaign_id)
        if conversation_id:
            filters.append(self.model.conversation_id == conversation_id)
        return await self.count_(filters=filters)

    async def get_by_id_for_update(
        self,
        call_id: UUID,
        organization_id: UUID,
    ) -> Optional[TelephonyCallModel]:
        query = select(self.model).where(
            self.model.id == call_id,
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        )
        result = await self.db_session.execute(query.with_for_update())
        return result.scalar_one_or_none()
