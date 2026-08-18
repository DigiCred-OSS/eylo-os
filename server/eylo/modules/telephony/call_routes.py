"""API routes for telephony call history."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.deletions.domain import DeletionTargetNotFound
from eylo.modules.deletions.schemas import DeletionJobApiResponse
from eylo.modules.telephony.call_controllers import TelephonyCallController
from eylo.modules.telephony.schemas import (
    TelephonyCallApiResponseSchema,
    TelephonyCallsPaginated,
)
from eylo.pipelines.deletions.request import DeletionRequestUseCase

from .constants import APP_TAG

router = APIRouter(prefix="/calls", tags=[APP_TAG])


@router.get("", response_model=TelephonyCallsPaginated)
async def list_calls(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by call status"),
    direction: Optional[str] = Query(None, description="Filter by call direction"),
    campaign_id: Optional[UUID] = Query(
        None, alias="campaignId", description="Filter by campaign ID"
    ),
    conversation_id: Optional[UUID] = Query(
        None, alias="conversationId", description="Filter by conversation ID"
    ),
) -> TelephonyCallsPaginated:
    async with start_transaction(ro=True):
        return await TelephonyCallController().list(
            current_user.organization_id,
            pagination,
            status,
            direction,
            campaign_id,
            conversation_id,
        )


@router.get("/{call_id}", response_model=TelephonyCallApiResponseSchema)
async def get_call(
    call_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> TelephonyCallApiResponseSchema:
    async with start_transaction(ro=True):
        return await TelephonyCallController().get(
            call_id,
            current_user.organization_id,
        )


@router.delete(
    "/{call_id}",
    response_model=DeletionJobApiResponse,
    status_code=status.HTTP_202_ACCEPTED,
    description="Accept asynchronous deletion of one owned call from Eylo",
)
async def delete_call(
    call_id: UUID,
    response: Response,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> DeletionJobApiResponse:
    try:
        result = await DeletionRequestUseCase().request_call(
            organization_id=current_user.organization_id,
            call_id=call_id,
            requested_by_member_id=current_user.member_id,
        )
    except DeletionTargetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        ) from None
    response.headers["Location"] = result.status_url
    return result
