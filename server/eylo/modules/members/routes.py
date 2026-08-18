"""HTTP routes for the `members` domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.members.controllers import MemberController
from eylo.modules.members.listing import (
    MemberListQuery,
    MemberSortDirection,
    MemberSortField,
)
from eylo.modules.members.models import MemberStatus
from eylo.modules.members.schemas.api import MemberApiResponseSchema, MembersPaginated

from .constants import APP_TAG

router = APIRouter(prefix="/{organization_id}/members", tags=[APP_TAG])


@router.get("", response_model=MembersPaginated)
async def list_members(
    organization_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[
        list[MemberStatus] | None,
        Query(alias="status"),
    ] = None,
    sort_by: Annotated[MemberSortField, Query()] = MemberSortField.CREATED_AT,
    sort_direction: Annotated[
        MemberSortDirection,
        Query(),
    ] = MemberSortDirection.DESC,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> MembersPaginated:
    return await MemberController().list_members(
        organization_id,
        pagination,
        current_user,
        query=MemberListQuery(
            search=search,
            statuses=tuple(status_filter or ()),
            sort_by=sort_by,
            sort_direction=sort_direction,
        ),
    )


@router.get("/{member_id}", response_model=MemberApiResponseSchema)
async def get_member(
    organization_id: UUID,
    member_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> MemberApiResponseSchema:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction(ro=True):
        return await MemberController().get(member_id, organization_id)
