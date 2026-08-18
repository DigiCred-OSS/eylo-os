"""Controller for campaign operations."""

import logging
from uuid import UUID

from fastapi import status
from fastapi.exceptions import HTTPException

from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionRevisionError, RevisionConflictError
from eylo.common.schemas import PaginationParams
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.contacts.domain import (
    ContactConflict,
    ContactDeletionPending,
    ContactNotFound,
)
from eylo.products.campaigns.domain import CampaignNotFoundError
from eylo.products.campaigns.schemas.api import (
    CampaignAnalyticsResponse,
    CampaignContactResponse,
    CampaignContactsPaginated,
    CampaignContactsSelectRequest,
    CampaignContactsUploadRequest,
    CampaignCreateRequest,
    CampaignPreparationResponse,
    CampaignResponse,
    CampaignRevisionRevokeRequest,
    CampaignUpdateRequest,
    CampaignsPaginated,
)
from eylo.products.campaigns.schemas.indb import CampaignUpdateSchema
from eylo.products.campaigns.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)


class CampaignController:
    """HTTP handler for campaign CRUD, state transitions, and contacts."""

    def __init__(self) -> None:
        self.service = CampaignService()

    def _check_org_access(
        self, organization_id: UUID, current_user: CurrentUserSchema
    ) -> None:
        if organization_id != current_user.organization_id:
            logger.warning(
                "Org access denied: user_org=%s requested_org=%s",
                current_user.organization_id,
                organization_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found.",
            )

    async def _get_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
    ):
        try:
            return await self.service.get_campaign(
                campaign_id,
                organization_id=organization_id,
            )
        except CampaignNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # ── Campaign CRUD ───────────────────────────────────────

    async def create_campaign(
        self,
        organization_id: UUID,
        request: CampaignCreateRequest,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        async with start_transaction():
            campaign = await self.service.create_campaign(
                organization_id=organization_id,
                name=request.name,
                agent_id=request.agent_id,
                description=request.description,
                channel=request.channel,
                channel_config=request.channel_config,
                initial_message_template_id=request.initial_message_template_id,
                schedule_config=request.schedule_config,
                retry_policy=request.retry_policy,
                concurrency_limit=request.concurrency_limit,
                published_by=current_user.member_id,
            )
            logger.info(
                "Campaign created: id=%s org=%s agent=%s",
                campaign.id,
                organization_id,
                request.agent_id,
            )
            return CampaignResponse.model_validate(campaign)

    async def get_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        async with start_transaction(ro=True):
            campaign = await self._get_campaign(organization_id, campaign_id)
            return CampaignResponse.model_validate(campaign)

    async def list_campaigns(
        self,
        organization_id: UUID,
        pagination: PaginationParams,
        current_user: CurrentUserSchema,
        status_filter: str | None = None,
    ) -> CampaignsPaginated:
        self._check_org_access(organization_id, current_user)
        async with start_transaction(ro=True):
            items, total = await self.service.list_campaigns(
                organization_id=organization_id,
                status=status_filter,
                offset=pagination.get_offset(),
                limit=pagination.limit,
            )
            return CampaignsPaginated(
                data=[CampaignResponse.model_validate(c) for c in items],
                page=pagination.page,
                limit=pagination.limit,
                total=total,
            )

    async def update_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        request: CampaignUpdateRequest,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                update_data = CampaignUpdateSchema(
                    **request.model_dump(exclude_unset=True)
                )
                updated = await self.service.update_campaign(
                    campaign_id,
                    update_data,
                    organization_id=organization_id,
                    published_by=current_user.member_id,
                )
                logger.info(
                    "Campaign updated: id=%s org=%s", campaign_id, organization_id
                )
                return CampaignResponse.model_validate(updated)
        except CampaignNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RevisionConflictError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except DefinitionRevisionError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except ValueError as error:
            logger.warning(
                "Campaign update rejected id=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )
            raise HTTPException(status_code=400, detail=str(error))

    async def delete_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> None:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                await self.service.delete_campaign(campaign_id)
                logger.info(
                    "Campaign deleted: id=%s org=%s", campaign_id, organization_id
                )
        except ValueError as error:
            logger.warning(
                "Campaign delete rejected id=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )
            raise HTTPException(status_code=400, detail=str(error))

    # ── State Transitions ───────────────────────────────────

    async def start_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        campaign = None
        pending_error = None
        try:
            async with start_transaction() as session:
                try:
                    await self._get_campaign(organization_id, campaign_id)
                    campaign = await self.service.start(
                        campaign_id,
                        organization_id=organization_id,
                    )
                except ContactDeletionPending as error:
                    await session.rollback()
                    pending_error = error
        except CampaignNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except DefinitionRevisionError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except ValueError as error:
            logger.warning(
                "Campaign start rejected id=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )
            raise HTTPException(status_code=400, detail=str(error))
        if pending_error is not None:
            raise HTTPException(
                status_code=409,
                detail="Campaign includes a deletion-pending contact",
            ) from pending_error
        assert campaign is not None
        logger.info("Campaign started: id=%s org=%s", campaign_id, organization_id)
        return CampaignResponse.model_validate(campaign)

    async def get_preparation(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignPreparationResponse:
        """Return warning/blocker counts without mutating the audience."""
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction(ro=True):
                preparation = await self.service.prepare_campaign(
                    campaign_id,
                    organization_id=organization_id,
                )
        except CampaignNotFoundError as error:
            raise HTTPException(status_code=404, detail="Campaign not found") from error
        return CampaignPreparationResponse.from_domain(
            campaign_id=campaign_id,
            preparation=preparation,
        )

    async def pause_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                campaign = await self.service.pause(campaign_id)
                logger.info(
                    "Campaign paused: id=%s org=%s", campaign_id, organization_id
                )
                return CampaignResponse.model_validate(campaign)
        except ValueError as error:
            logger.warning(
                "Campaign pause rejected id=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )
            raise HTTPException(status_code=400, detail=str(error))

    async def cancel_campaign(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignResponse:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                campaign = await self.service.cancel(campaign_id)
                logger.info(
                    "Campaign canceled: id=%s org=%s", campaign_id, organization_id
                )
                return CampaignResponse.model_validate(campaign)
        except ValueError as error:
            logger.warning(
                "Campaign cancel rejected id=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )
            raise HTTPException(status_code=400, detail=str(error))

    async def revoke_campaign_revision(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        revision: int,
        request: CampaignRevisionRevokeRequest,
        current_user: CurrentUserSchema,
    ) -> None:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self.service.revoke_revision(
                    campaign_id,
                    revision,
                    organization_id=organization_id,
                    actor_id=current_user.member_id,
                    reason=request.reason,
                )
        except CampaignNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error))
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error))

    # ── Contact Management ──────────────────────────────────

    async def upload_contacts(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        request: CampaignContactsUploadRequest,
        current_user: CurrentUserSchema,
    ) -> dict:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                count = await self.service.upload_contacts(
                    campaign_id=campaign_id,
                    organization_id=organization_id,
                    rows=request.contacts,
                )
                logger.info(
                    "Contacts uploaded: campaign=%s count=%d org=%s",
                    campaign_id,
                    count,
                    organization_id,
                )
                return {"added": count}
        except ContactNotFound as error:
            raise HTTPException(status_code=404, detail="Contact not found") from error
        except ContactDeletionPending as error:
            raise HTTPException(
                status_code=409,
                detail="Contact deletion is pending",
            ) from error
        except ContactConflict as error:
            raise HTTPException(
                status_code=409,
                detail="Contact identity already exists",
            ) from error
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def select_contacts(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        request: CampaignContactsSelectRequest,
        current_user: CurrentUserSchema,
    ) -> dict:
        self._check_org_access(organization_id, current_user)
        try:
            async with start_transaction():
                await self._get_campaign(organization_id, campaign_id)
                count = await self.service.select_contacts(
                    campaign_id=campaign_id,
                    organization_id=organization_id,
                    contact_ids=request.contact_ids,
                )
                logger.info(
                    "Contacts selected: campaign=%s count=%d org=%s",
                    campaign_id,
                    count,
                    organization_id,
                )
                return {"added": count}
        except ContactNotFound as error:
            raise HTTPException(status_code=404, detail="Contact not found") from error
        except ContactDeletionPending as error:
            raise HTTPException(
                status_code=409,
                detail="Contact deletion is pending",
            ) from error
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def list_contacts(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        pagination: PaginationParams,
        current_user: CurrentUserSchema,
        status_filter: str | None = None,
    ) -> CampaignContactsPaginated:
        self._check_org_access(organization_id, current_user)
        async with start_transaction(ro=True):
            await self._get_campaign(organization_id, campaign_id)
            items, total = await self.service.list_contacts(
                campaign_id=campaign_id,
                status=status_filter,
                offset=pagination.get_offset(),
                limit=pagination.limit,
            )
            return CampaignContactsPaginated(
                data=[CampaignContactResponse.model_validate(c) for c in items],
                page=pagination.page,
                limit=pagination.limit,
                total=total,
            )

    # ── Analytics ───────────────────────────────────────────

    async def get_analytics(
        self,
        organization_id: UUID,
        campaign_id: UUID,
        current_user: CurrentUserSchema,
    ) -> CampaignAnalyticsResponse:
        self._check_org_access(organization_id, current_user)
        async with start_transaction(ro=True):
            campaign = await self._get_campaign(organization_id, campaign_id)

            status_summary = await self.service.get_contact_status_summary(campaign_id)
            outcome_dist = await self.service.get_outcome_distribution(campaign_id)

            return CampaignAnalyticsResponse(
                campaign_id=campaign_id,
                total_contacts=campaign.total_contacts or 0,
                completed=status_summary.get("completed", 0),
                failed=status_summary.get("failed", 0),
                pending=status_summary.get("pending", 0),
                retry=status_summary.get("retry", 0),
                skipped=status_summary.get("skipped", 0),
                connect_rate=self._compute_connect_rate(status_summary),
                outcome_distribution=outcome_dist,
            )

    @staticmethod
    def _compute_connect_rate(status_summary: dict[str, int]) -> float:
        """Compute connect rate from status breakdown."""
        completed = status_summary.get("completed", 0)
        failed = status_summary.get("failed", 0)
        total_attempted = completed + failed
        if total_attempted == 0:
            return 0.0
        return round(completed / total_attempted * 100, 1)
