"""Persistence access for the `contacts` domain."""

from uuid import UUID

from sqlalchemy import or_, select

from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.modules.contacts.domain import ContactLifecycle, ContactNotFound
from eylo.modules.contacts.schemas.indb import (
    ContactCreateSchema,
    ContactRef,
    ContactUpdateSchema,
)

from .models import ContactsModel


class ContactsRepository(BaseORMRepository[ContactsModel]):
    """ContactsRepository behavior for the "contacts" domain."""

    @property
    def model(self):
        """Model for the "contacts" domain."""
        return ContactsModel

    async def create_(self, data: ContactCreateSchema) -> ContactsModel:
        """Create for the "contacts" domain."""
        contact = map_schema_to_model(ContactsModel, data)
        return await self.save_(contact)

    async def get_by_ref(self, ref: ContactRef) -> ContactsModel | None:
        """Resolve one active contact through its immutable tenant reference."""
        return await self.filter_one_(
            [
                self.model.id == ref.contact_id,
                self.model.organization_id == ref.organization_id,
                self.model.deleted.is_(False),
                self.model.lifecycle == ContactLifecycle.ACTIVE.value,
            ]
        )

    async def get_member_by_ref(
        self,
        ref: ContactRef,
        *,
        for_update: bool = False,
    ) -> ContactsModel | None:
        """Load an owned non-erased contact, including a pending deletion."""
        statement = select(self.model).where(
            self.model.id == ref.contact_id,
            self.model.organization_id == ref.organization_id,
            self.model.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db_session.scalar(statement)

    async def find_identity_matches(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID | None = None,
        external_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[ContactsModel]:
        """Load every active same-org row matched by a supplied identifier."""
        identity_filters = []
        if contact_id is not None:
            identity_filters.append(self.model.id == contact_id)
        if external_id is not None:
            identity_filters.append(self.model.external_id == external_id)
        if email is not None:
            identity_filters.append(self.model.primary_email == email)
        if phone is not None:
            identity_filters.append(self.model.primary_phone == phone)
        if not identity_filters:
            return []

        return await self.filter_all_(
            filters=[
                self.model.organization_id == organization_id,
                self.model.deleted.is_(False),
                or_(*identity_filters),
            ]
        )

    async def update_(
        self,
        data: ContactUpdateSchema,
        *,
        contact: ContactsModel | None = None,
    ) -> ContactsModel:
        """Update for the "contacts" domain."""
        ref = ContactRef(
            organization_id=data.organization_id,
            contact_id=data.id,
        )
        contact = contact or await self.get_member_by_ref(ref, for_update=True)
        if not contact:
            raise ContactNotFound("Contact not found")

        changes = data.model_dump(
            exclude={"id", "organization_id"},
            exclude_unset=True,
        )
        for field, value in changes.items():
            if value != getattr(contact, field):
                setattr(contact, field, value)
        return await self.save_(contact)

    async def list_by_ids(
        self,
        contact_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ContactsModel]:
        """Bulk fetch contacts by IDs within an organization.

        Args:
            contact_ids: List of contact IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of contact models matching the IDs

        """
        if not contact_ids:
            return []

        filters = [
            self.model.id.in_(contact_ids),
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        ]
        return await self.filter_all_(filters=filters)
