"""File durable outreach attempts for running campaigns."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import DEFAULT_MAX_ATTEMPTS
from eylo.products.campaigns.constants import CampaignContactStatus, CampaignStatus
from eylo.products.campaigns.models import CampaignAttemptModel
from eylo.products.campaigns.repositories import (
    CampaignContactRepository,
    CampaignRepository,
)
from eylo.products.campaigns.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)


class CampaignExecutionService:
    """Atomically file provider effects; never dispatch a channel itself."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._campaign_repo = CampaignRepository(db=db)
        self._contact_repo = CampaignContactRepository(db=db)
        self._campaign_service = CampaignService(db=db)
        self._db = self._campaign_repo.db_session

    async def file_due_attempts(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        now: datetime,
    ) -> list[CampaignAttemptModel]:
        """Reserve available contact slots as exact durable attempt rows."""
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
            for_update=True,
        )
        if campaign is None or campaign.status != CampaignStatus.RUNNING.value:
            return []
        if campaign.active_revision is None:
            raise ValueError("Running campaign has no active definition revision.")

        definition = await self._campaign_service.get_definition_revision(
            organization_id=organization_id,
            campaign_id=campaign_id,
            revision=campaign.active_revision,
        )
        active = await self._contact_repo.count_by_campaign(
            campaign_id,
            status=CampaignContactStatus.IN_PROGRESS.value,
        )
        queued = await self._contact_repo.count_by_campaign(
            campaign_id,
            status=CampaignContactStatus.QUEUED.value,
        )
        slots_available = definition.concurrency_limit - active - queued
        if slots_available <= 0:
            return []

        contacts = await self._contact_repo.get_next_batch(
            campaign_id,
            now=now,
            limit=slots_available,
        )
        attempts: list[CampaignAttemptModel] = []
        for contact in contacts:
            revision = contact.campaign_revision or definition.revision
            attempt_definition = definition
            if revision != definition.revision:
                attempt_definition = (
                    await self._campaign_service.get_definition_revision(
                        organization_id=organization_id,
                        campaign_id=campaign_id,
                        revision=revision,
                    )
                )
            attempt = CampaignAttemptModel(
                organization_id=organization_id,
                campaign_id=campaign_id,
                campaign_contact_id=contact.id,
                campaign_revision=revision,
                attempt_number=(contact.attempt_count or 0) + 1,
                channel=attempt_definition.channel,
                max_attempts=DEFAULT_MAX_ATTEMPTS,
            )
            self._db.add(attempt)
            contact.campaign_revision = revision
            contact.status = CampaignContactStatus.QUEUED.value
            contact.next_retry_at = None
            attempts.append(attempt)

        await self._db.flush()
        if not attempts:
            await self._complete_if_terminal(campaign_id)
        return attempts

    async def _complete_if_terminal(self, campaign_id: UUID) -> None:
        status_counts = await self._contact_repo.count_by_status(campaign_id)
        non_terminal = sum(
            status_counts.get(state.value, 0)
            for state in (
                CampaignContactStatus.PENDING,
                CampaignContactStatus.QUEUED,
                CampaignContactStatus.IN_PROGRESS,
                CampaignContactStatus.RETRY,
            )
        )
        if non_terminal == 0 and sum(status_counts.values()) > 0:
            await self._campaign_service.transition(
                campaign_id,
                CampaignStatus.COMPLETED,
            )


__all__ = ["CampaignExecutionService"]
