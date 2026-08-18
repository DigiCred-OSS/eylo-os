"""HTTP routes for the `contacts` domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.contacts.controllers.api_controller import ContactController
from eylo.modules.contacts.domain import ContactLifecycle
from eylo.modules.contacts.listing import (
    ContactListQuery,
    ContactSortDirection,
    ContactSortField,
)
from eylo.modules.contacts.schemas.api import (
    ContactApiResponseSchema,
    ContactCreateRequestSchema,
    ContactPatchRequestSchema,
    ContactsPaginated,
)
from eylo.modules.deletions.schemas import DeletionJobApiResponse

from .constants import APP_TAG

router = APIRouter(prefix="/{organization_id}/contacts", tags=[APP_TAG])


@router.get(
    "",
    response_model=ContactsPaginated,
    description="Get a connection by Connection ID",
)
async def list_contacts(
    organization_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    contact_ids: Annotated[list[UUID] | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    lifecycle: Annotated[list[ContactLifecycle] | None, Query()] = None,
    sort_by: Annotated[ContactSortField, Query()] = ContactSortField.UPDATED_AT,
    sort_direction: Annotated[
        ContactSortDirection,
        Query(),
    ] = ContactSortDirection.DESC,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ContactsPaginated:
    return await ContactController().list_contacts(
        organization_id,
        ContactListQuery(
            contact_ids=tuple(contact_ids or ()),
            search=search,
            lifecycles=tuple(lifecycle or ()),
            sort_by=sort_by,
            sort_direction=sort_direction,
        ),
        pagination,
        current_user,
    )


@router.get(
    "/{contact_id}",
    response_model=ContactApiResponseSchema,
    description="Get contact by ID",
)
async def get_contact(
    organization_id: UUID,
    contact_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    return await ContactController().get_contact(
        organization_id, contact_id, current_user
    )


@router.post(
    "",
    response_model=ContactApiResponseSchema,
    status_code=status.HTTP_201_CREATED,
    description="Create a new connection",
)
async def create_contact(
    organization_id: UUID,
    request: ContactCreateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    return await ContactController().create_contact(
        organization_id,
        request,
        current_user,
    )


@router.patch(
    "/{contact_id}",
    response_model=ContactApiResponseSchema,
    description="Patch maintained fields on an owned contact",
)
async def update_contact(
    organization_id: UUID,
    contact_id: UUID,
    request: ContactPatchRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ContactApiResponseSchema:
    return await ContactController().update_contact(
        organization_id,
        contact_id,
        request,
        current_user,
    )


@router.delete(
    "/{contact_id}",
    response_model=DeletionJobApiResponse,
    status_code=status.HTTP_202_ACCEPTED,
    description="Fence an owned contact and accept asynchronous Eylo deletion",
)
async def delete_contact(
    organization_id: UUID,
    contact_id: UUID,
    response: Response,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> DeletionJobApiResponse:
    result = await ContactController().request_contact_deletion(
        organization_id,
        contact_id,
        current_user,
    )
    response.headers["Location"] = result.status_url
    return result
