"""Repository for campaign database operations."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import uuid_utils
from sqlalchemy import func, insert, select, update

from eylo.common.repositories import BaseORMRepository
from eylo.products.campaigns.constants import CampaignContactStatus, CampaignStatus
from eylo.products.campaigns.models import (
    CampaignContactModel,
    CampaignModel,
    CampaignRevisionModel,
)
from eylo.products.campaigns.schemas.indb import (
    CampaignContactCreateSchema,
    CampaignCreateSchema,
    CampaignUpdateSchema,
)


class CampaignRepository(BaseORMRepository[CampaignModel]):
    """Data access layer for campaigns."""

    @property
    def model(self) -> type[CampaignModel]:
        return CampaignModel

    async def create(
        self, organization_id: UUID, request: CampaignCreateSchema
    ) -> CampaignModel:
        campaign = self.model(
            organization_id=organization_id,
            **request.model_dump(exclude={"organization_id"}),
        )
        return await self.save_(campaign)

    async def update(
        self, campaign_id: UUID, request: CampaignUpdateSchema
    ) -> CampaignModel:
        campaign = await self.get_(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")

        update_data = request.model_dump(
            exclude_unset=True,
            exclude={"expected_revision"},
        )
        for key, value in update_data.items():
            setattr(campaign, key, value)

        return await self.partial_update_(entity=campaign)

    async def get_scoped(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        for_update: bool = False,
    ) -> CampaignModel | None:
        stmt = select(self.model).where(
            self.model.organization_id == organization_id,
            self.model.id == campaign_id,
            self.model.deleted.is_(False),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.db_session.scalar(stmt)

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        revision: int,
        for_update: bool = False,
    ) -> CampaignRevisionModel | None:
        stmt = select(CampaignRevisionModel).where(
            CampaignRevisionModel.organization_id == organization_id,
            CampaignRevisionModel.campaign_id == campaign_id,
            CampaignRevisionModel.revision == revision,
            CampaignRevisionModel.deleted.is_(False),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return await self.db_session.scalar(stmt)

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, **kwargs
    ) -> CampaignModel:
        """Update campaign status with optional extra fields (started_at, completed_at)."""
        campaign = await self.get_(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")

        campaign.status = status.value
        for key, value in kwargs.items():
            setattr(campaign, key, value)

        return await self.partial_update_(entity=campaign)

    async def list_by_organization(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[CampaignModel]:
        stmt = (
            select(self.model)
            .where(
                self.model.organization_id == organization_id,
                self.model.deleted.is_(False),
            )
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(self.model.status == status)

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(
        self, organization_id: UUID, status: Optional[str] = None
    ) -> int:
        stmt = select(func.count(self.model.id)).where(
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        )
        if status:
            stmt = stmt.where(self.model.status == status)

        result = await self.db_session.execute(stmt)
        return result.scalar_one()

    async def list_running(self) -> List[CampaignModel]:
        """List all campaigns in RUNNING status (for the execution engine)."""
        stmt = select(self.model).where(
            self.model.status == CampaignStatus.RUNNING.value,
            self.model.deleted.is_(False),
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def increment_counters(
        self,
        campaign_id: UUID,
        completed_delta: int = 0,
        failed_delta: int = 0,
    ) -> None:
        """Atomically increment denormalized counters."""
        values = {}
        if completed_delta:
            values["completed_contacts"] = (
                CampaignModel.completed_contacts + completed_delta
            )
        if failed_delta:
            values["failed_contacts"] = CampaignModel.failed_contacts + failed_delta

        if values:
            stmt = (
                update(CampaignModel)
                .where(CampaignModel.id == campaign_id)
                .values(**values)
            )
            await self.db_session.execute(stmt)

    async def set_total_contacts(self, campaign_id: UUID, total: int) -> None:
        await self.db_session.execute(
            update(CampaignModel)
            .where(CampaignModel.id == campaign_id)
            .values(total_contacts=total)
        )


class CampaignContactRepository(BaseORMRepository[CampaignContactModel]):
    """Data access layer for campaign contacts."""

    @property
    def model(self) -> type[CampaignContactModel]:
        return CampaignContactModel

    async def bulk_create(
        self,
        campaign_id: UUID,
        organization_id: UUID,
        contacts: List[CampaignContactCreateSchema],
    ) -> int:
        """Bulk insert campaign contacts using raw INSERT. Returns count."""
        import uuid as _uuid

        if not contacts:
            return 0

        rows = []
        for c in contacts:
            rows.append(
                {
                    "id": _uuid.UUID(str(uuid_utils.uuid7())),
                    "campaign_id": campaign_id,
                    "organization_id": organization_id,
                    "contact_address": c.contact_address,
                    "contact_id": (
                        _uuid.UUID(str(c.contact_id)) if c.contact_id else None
                    ),
                    "variables": c.variables,
                    "status": CampaignContactStatus.PENDING.value,
                }
            )

        await self.db_session.execute(insert(self.model), rows)
        return len(rows)

    async def list_by_campaign(
        self,
        campaign_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[CampaignContactModel]:
        stmt = (
            select(self.model)
            .where(
                self.model.campaign_id == campaign_id,
                self.model.deleted.is_(False),
            )
            .order_by(self.model.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(self.model.status == status)

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def list_preparation_page(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        offset: int,
        limit: int,
    ) -> List[CampaignContactModel]:
        """Load one stable tenant-scoped audience page for preparation."""
        result = await self.db_session.scalars(
            select(self.model)
            .where(
                self.model.organization_id == organization_id,
                self.model.campaign_id == campaign_id,
                self.model.deleted.is_(False),
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def count_by_campaign(
        self, campaign_id: UUID, status: Optional[str] = None
    ) -> int:
        stmt = select(func.count(self.model.id)).where(
            self.model.campaign_id == campaign_id,
            self.model.deleted.is_(False),
        )
        if status:
            stmt = stmt.where(self.model.status == status)

        result = await self.db_session.execute(stmt)
        return result.scalar_one()

    async def count_by_status(self, campaign_id: UUID) -> dict[str, int]:
        """Return {status: count} for all contacts in a campaign."""
        stmt = (
            select(self.model.status, func.count(self.model.id))
            .where(
                self.model.campaign_id == campaign_id,
                self.model.deleted.is_(False),
            )
            .group_by(self.model.status)
        )
        result = await self.db_session.execute(stmt)
        return dict(result.all())

    async def get_next_batch(
        self, campaign_id: UUID, now: datetime, limit: int
    ) -> List[CampaignContactModel]:
        """Get the next batch of contacts to schedule for calling.

        Returns contacts that are PENDING, or RETRY with next_retry_at <= now.
        Uses FOR UPDATE SKIP LOCKED to prevent duplicate scheduling.
        """
        stmt = (
            select(self.model)
            .where(
                self.model.campaign_id == campaign_id,
                self.model.deleted.is_(False),
            )
            .where(
                (self.model.status == CampaignContactStatus.PENDING.value)
                | (
                    (self.model.status == CampaignContactStatus.RETRY.value)
                    & (self.model.next_retry_at <= now)
                )
            )
            .order_by(self.model.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def update_contact_status(
        self,
        contact_id: UUID,
        status: CampaignContactStatus,
        **kwargs,
    ) -> CampaignContactModel:
        """Update a campaign contact's status with optional extra fields."""
        contact = await self.get_(contact_id)
        if not contact:
            raise ValueError("Campaign contact not found")

        contact.status = status.value
        for key, value in kwargs.items():
            setattr(contact, key, value)

        return await self.partial_update_(entity=contact)

    async def find_by_tracking_id(
        self, campaign_id: UUID, tracking_id: str
    ) -> Optional[CampaignContactModel]:
        """Find a campaign contact by its last tracking ID."""
        stmt = select(self.model).where(
            self.model.campaign_id == campaign_id,
            self.model.last_tracking_id == tracking_id,
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def outcome_distribution(self, campaign_id: UUID) -> dict[str, int]:
        """Return {outcome_reason: count} for all completed/failed contacts."""
        stmt = (
            select(self.model.last_outcome_reason, func.count(self.model.id))
            .where(
                self.model.campaign_id == campaign_id,
                self.model.last_outcome_reason.isnot(None),
            )
            .group_by(self.model.last_outcome_reason)
        )
        result = await self.db_session.execute(stmt)
        return dict(result.all())
