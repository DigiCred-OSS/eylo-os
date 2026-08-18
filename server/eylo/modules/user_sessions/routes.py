"""Member-private user-session list, detail, and timeline routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.user_sessions.domain import (
    UserSessionEntryChannel,
    UserSessionNotFound,
    UserSessionState,
)
from eylo.modules.user_sessions.listing import (
    UserSessionListQuery,
    UserSessionQueryService,
    UserSessionSortDirection,
    UserSessionSortField,
)
from eylo.modules.user_sessions.schemas import (
    TimelineCategory,
    UserSessionPage,
    UserSessionRead,
    UserSessionTimelinePage,
)
from eylo.modules.user_sessions.timeline import ALLOWED_TIMELINE_EVENT_TYPES

router = APIRouter(prefix="/{organization_id}/sessions", tags=["User sessions"])


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    """Hide foreign-tenant session surfaces behind the normal 404 boundary."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("", response_model=UserSessionPage)
async def list_user_sessions(
    organization_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    contact_id: Annotated[UUID | None, Query()] = None,
    state: Annotated[list[UserSessionState] | None, Query(max_length=4)] = None,
    entry_channel: Annotated[
        list[UserSessionEntryChannel] | None,
        Query(max_length=3),
    ] = None,
    started_from: Annotated[datetime | None, Query()] = None,
    started_to: Annotated[datetime | None, Query()] = None,
    sort_by: Annotated[UserSessionSortField, Query()] = (
        UserSessionSortField.STARTED_AT
    ),
    sort_direction: Annotated[UserSessionSortDirection, Query()] = (
        UserSessionSortDirection.DESC
    ),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> UserSessionPage:
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True) as session:
        return await UserSessionQueryService(session).list(
            organization_id=organization_id,
            query=UserSessionListQuery(
                search=search,
                contact_id=contact_id,
                states=tuple(state or ()),
                entry_channels=tuple(entry_channel or ()),
                started_from=started_from,
                started_to=started_to,
                sort_by=sort_by,
                sort_direction=sort_direction,
            ),
            page=pagination.page,
            limit=pagination.limit,
        )


@router.get("/{user_session_id}", response_model=UserSessionRead)
async def get_user_session(
    organization_id: UUID,
    user_session_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> UserSessionRead:
    _authorize(organization_id, current_user)
    try:
        async with start_transaction(ro=True) as session:
            return await UserSessionQueryService(session).get(
                organization_id=organization_id,
                user_session_id=user_session_id,
            )
    except UserSessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from None


@router.get(
    "/{user_session_id}/timeline",
    response_model=UserSessionTimelinePage,
)
async def get_user_session_timeline(
    organization_id: UUID,
    user_session_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    category: Annotated[list[TimelineCategory] | None, Query(max_length=9)] = None,
    event_type: Annotated[list[str] | None, Query(max_length=50)] = None,
    include_technical: Annotated[bool, Query()] = False,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> UserSessionTimelinePage:
    _authorize(organization_id, current_user)
    requested_types = set(event_type or ())
    if not requested_types.issubset(ALLOWED_TIMELINE_EVENT_TYPES):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Timeline event type is not supported.",
        )
    try:
        async with start_transaction(ro=True) as session:
            return await UserSessionQueryService(session).timeline(
                organization_id=organization_id,
                user_session_id=user_session_id,
                categories=set(category or ()),
                event_types=requested_types,
                include_technical=include_technical,
                page=pagination.page,
                limit=pagination.limit,
            )
    except UserSessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from None


__all__ = ["router"]
