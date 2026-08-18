"""REST API routes for campaigns."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eylo.common.revisions import DefinitionRevisionError
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.products.campaigns.controllers import CampaignController
from eylo.products.campaigns.schemas.api import (
    CampaignAnalyticsResponse,
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

APP_TAG = "Campaigns"

router = APIRouter(prefix="/{organization_id}/campaigns", tags=[APP_TAG])


# ── Campaign CRUD ───────────────────────────────────────────


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new campaign",
)
async def create_campaign(
    organization_id: UUID,
    request: CampaignCreateRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    try:
        return await CampaignController().create_campaign(
            organization_id, request, current_user
        )
    except DefinitionRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get(
    "",
    response_model=CampaignsPaginated,
    description="List campaigns for an organization",
)
async def list_campaigns(
    organization_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> CampaignsPaginated:
    return await CampaignController().list_campaigns(
        organization_id, pagination, current_user, status_filter
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    description="Get campaign details",
)
async def get_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    return await CampaignController().get_campaign(
        organization_id, campaign_id, current_user
    )


@router.put(
    "/{campaign_id}",
    response_model=CampaignResponse,
    description="Update a campaign (DRAFT or PAUSED only)",
)
async def update_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    request: CampaignUpdateRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    return await CampaignController().update_campaign(
        organization_id, campaign_id, request, current_user
    )


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete a campaign (DRAFT or CANCELED only)",
)
async def delete_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> None:
    await CampaignController().delete_campaign(
        organization_id, campaign_id, current_user
    )


# ── State Transitions ──────────────────────────────────────


@router.get(
    "/{campaign_id}/preparation",
    response_model=CampaignPreparationResponse,
    description="Inspect warning-only audience preparation without filtering contacts",
)
async def get_campaign_preparation(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignPreparationResponse:
    return await CampaignController().get_preparation(
        organization_id,
        campaign_id,
        current_user,
    )


@router.post(
    "/{campaign_id}/start",
    response_model=CampaignResponse,
    description="Start a campaign (DRAFT/PAUSED → RUNNING)",
)
async def start_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    return await CampaignController().start_campaign(
        organization_id, campaign_id, current_user
    )


@router.post(
    "/{campaign_id}/pause",
    response_model=CampaignResponse,
    description="Pause a running campaign",
)
async def pause_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    return await CampaignController().pause_campaign(
        organization_id, campaign_id, current_user
    )


@router.post(
    "/{campaign_id}/cancel",
    response_model=CampaignResponse,
    description="Cancel a campaign",
)
async def cancel_campaign(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignResponse:
    return await CampaignController().cancel_campaign(
        organization_id, campaign_id, current_user
    )


@router.post(
    "/{campaign_id}/revisions/{revision}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Emergency-revoke an exact campaign revision",
)
async def revoke_campaign_revision(
    organization_id: UUID,
    campaign_id: UUID,
    revision: int,
    request: CampaignRevisionRevokeRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> None:
    await CampaignController().revoke_campaign_revision(
        organization_id,
        campaign_id,
        revision,
        request,
        current_user,
    )


# ── Contact Management ─────────────────────────────────────


@router.post(
    "/{campaign_id}/contacts",
    description="Upload contacts to a campaign",
)
async def upload_contacts(
    organization_id: UUID,
    campaign_id: UUID,
    request: CampaignContactsUploadRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> dict:
    return await CampaignController().upload_contacts(
        organization_id, campaign_id, request, current_user
    )


@router.post(
    "/{campaign_id}/contacts/select",
    description="Add existing contacts to a campaign by their IDs",
)
async def select_contacts(
    organization_id: UUID,
    campaign_id: UUID,
    request: CampaignContactsSelectRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> dict:
    return await CampaignController().select_contacts(
        organization_id, campaign_id, request, current_user
    )


@router.get(
    "/{campaign_id}/contacts",
    response_model=CampaignContactsPaginated,
    description="List contacts in a campaign",
)
async def list_contacts(
    organization_id: UUID,
    campaign_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> CampaignContactsPaginated:
    return await CampaignController().list_contacts(
        organization_id, campaign_id, pagination, current_user, status_filter
    )


# ── Analytics ───────────────────────────────────────────────


@router.get(
    "/{campaign_id}/analytics",
    response_model=CampaignAnalyticsResponse,
    description="Get campaign analytics and outcome distribution",
)
async def get_analytics(
    organization_id: UUID,
    campaign_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> CampaignAnalyticsResponse:
    return await CampaignController().get_analytics(
        organization_id, campaign_id, current_user
    )
