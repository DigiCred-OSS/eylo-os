"""Controller for handling contact-related operations."""

from typing import NoReturn
from uuid import UUID

from fastapi import status
from fastapi.exceptions import HTTPException

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.contacts.domain import (
    ContactActorKind,
    ContactConflict,
    ContactDeletionPending,
    ContactError,
    ContactIdentityInvalid,
    ContactNotFound,
)
from eylo.modules.contacts.listing import ContactListQuery
from eylo.modules.contacts.schemas.api import (
    ContactApiResponseSchema,
    ContactCreateRequestSchema,
    ContactPatchRequestSchema,
    ContactsPaginated,
)
from eylo.modules.contacts.schemas.indb import (
    ContactCreateSchema,
    ContactRef,
    ContactUpdateSchema,
)
from eylo.modules.contacts.service import ContactService
from eylo.modules.deletions.domain import DeletionTargetNotFound
from eylo.modules.deletions.schemas import DeletionJobApiResponse
from eylo.pipelines.deletions.request import DeletionRequestUseCase


class ContactController:
    """Controller for handling contact-related operations."""

    def __init__(self):
        """Initialize the ContactController."""
        self.service = ContactService()

    @staticmethod
    def _member_organization(
        organization_id: UUID,
        current_user: CurrentUserSchema,
    ) -> UUID:
        if organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found",
            )
        return current_user.organization_id

    @staticmethod
    def _raise_http(error: ContactError) -> NoReturn:
        if isinstance(error, ContactNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found",
            ) from error
        if isinstance(error, ContactDeletionPending):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact deletion is pending",
            ) from error
        if isinstance(error, ContactConflict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact identity already exists",
            ) from error
        if isinstance(error, ContactIdentityInvalid):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Contact identifier is invalid",
            ) from error
        raise AssertionError("Unhandled contact error")

    async def list_contacts(
        self,
        organization_id: UUID,
        query: ContactListQuery,
        pagination: PaginationParams,
        current_user: CurrentUserSchema,
    ) -> ContactsPaginated:
        """List contacts for an organization."""
        organization_id = self._member_organization(organization_id, current_user)
        async with start_transaction(ro=True):
            # Bulk fetch by IDs if contact_ids filter provided
            if query.contact_ids:
                contacts = await self.service.list_by_ids(
                    contact_ids=list(query.contact_ids),
                    organization_id=organization_id,
                )
                contacts = [
                    ContactApiResponseSchema.model_validate(contact)
                    for contact in contacts
                ]
                return ContactsPaginated(
                    data=contacts,
                    limit=len(contacts),
                    page=1,
                    total=len(contacts),
                )

            # Regular paginated list
            contacts = await self.service.list_by_organization(
                organization_id=organization_id,
                limit=pagination.limit,
                offset=pagination.get_offset(),
                query=query,
            )
            contacts = [
                ContactApiResponseSchema.model_validate(contact) for contact in contacts
            ]
            count = await self.service.count_by_organization(
                organization_id=organization_id,
                query=query,
            )
            return ContactsPaginated(
                data=contacts,
                limit=pagination.limit,
                page=pagination.page,
                total=count,
                has_more=pagination.get_offset() + len(contacts) < count,
            )

    async def get_contact(
        self,
        organization_id: UUID,
        contact_id: UUID,
        current_user: CurrentUserSchema,
    ) -> ContactApiResponseSchema:
        """Get a contact by its ID."""
        organization_id = self._member_organization(organization_id, current_user)
        async with start_transaction(ro=True):
            contact = await self.service.get_member_by_ref(
                ContactRef(
                    organization_id=organization_id,
                    contact_id=contact_id,
                )
            )
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found",
            )
        return ContactApiResponseSchema.model_validate(contact)

    async def create_contact(
        self,
        organization_id: UUID,
        request: ContactCreateRequestSchema,
        current_user: CurrentUserSchema,
    ):
        """Create a new contact."""
        organization_id = self._member_organization(organization_id, current_user)
        contact = None
        expected_error = None
        async with start_transaction() as session:
            try:
                contact = await self.service.create_(
                    ContactCreateSchema(
                        organization_id=organization_id,
                        **request.model_dump(),
                    ),
                    actor_kind=ContactActorKind.MEMBER,
                    actor_id=current_user.member_id,
                )
            except ContactError as error:
                await session.rollback()
                expected_error = error
        if expected_error is not None:
            self._raise_http(expected_error)
        assert contact is not None
        return ContactApiResponseSchema.model_validate(contact)

    async def update_contact(
        self,
        organization_id: UUID,
        contact_id: UUID,
        request: ContactPatchRequestSchema,
        current_user: CurrentUserSchema,
    ) -> ContactApiResponseSchema:
        """Patch one owned active contact."""
        organization_id = self._member_organization(organization_id, current_user)
        contact = None
        expected_error = None
        async with start_transaction() as session:
            try:
                contact = await self.service.update_(
                    ContactUpdateSchema(
                        id=contact_id,
                        organization_id=organization_id,
                        **request.model_dump(exclude_unset=True),
                    ),
                    actor_kind=ContactActorKind.MEMBER,
                    actor_id=current_user.member_id,
                )
            except ContactError as error:
                await session.rollback()
                expected_error = error
        if expected_error is not None:
            self._raise_http(expected_error)
        assert contact is not None
        return ContactApiResponseSchema.model_validate(contact)

    async def request_contact_deletion(
        self,
        organization_id: UUID,
        contact_id: UUID,
        current_user: CurrentUserSchema,
    ) -> DeletionJobApiResponse:
        """Fence one owned contact before its durable erasure job runs."""
        organization_id = self._member_organization(organization_id, current_user)
        try:
            return await DeletionRequestUseCase().request_contact(
                organization_id=organization_id,
                contact_id=contact_id,
                requested_by_member_id=current_user.member_id,
            )
        except DeletionTargetNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found",
            ) from None
