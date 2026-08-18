"""Application services for the `contacts` domain."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, override
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.phone_numbers import PhoneNumberNormalizationService
from eylo.common.services import EyloBaseService
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventService
from eylo.modules.contacts.domain import (
    CONTACT_SUBJECT_TYPE,
    ContactActorKind,
    ContactConflict,
    ContactDeletionPending,
    ContactIdentityInvalid,
    ContactLifecycle,
    ContactNotFound,
)
from eylo.modules.contacts.listing import (
    ContactListQuery,
    ContactSortDirection,
    ContactSortField,
)
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.contacts.schemas.indb import (
    ContactCreateSchema,
    ContactInDb,
    ContactRef,
    ContactUpdateSchema,
)

from .repositories import ContactsRepository


class ContactIdentifierKind(str, Enum):
    """Identify-time priority vocabulary exposed without another contact ID."""

    CONTACT_ID = "contact_id"
    EXTERNAL_ID = "external_id"
    EMAIL = "email"
    PHONE = "phone"


@dataclass(frozen=True, slots=True)
class ContactIdentity:
    """Canonical identify-time values in their fixed priority order."""

    organization_id: UUID
    contact_id: UUID | None = None
    external_id: str | None = None
    email: str | None = None
    phone: str | None = None


@dataclass(frozen=True, slots=True)
class ContactResolution:
    """Priority winner plus safe ambiguity facts for product presentation."""

    contact: ContactInDb | None
    matched_by: ContactIdentifierKind | None
    conflicting_identifiers: tuple[ContactIdentifierKind, ...] = ()
    created: bool = False

    @property
    def warning_codes(self) -> tuple[str, ...]:
        return tuple(
            f"contact_identifier_conflict:{identifier.value}"
            for identifier in self.conflicting_identifiers
        )


class ContactService(EyloBaseService[ContactInDb]):
    """ContactService behavior for the "contacts" domain."""

    @property
    @override
    def schema(self) -> type[ContactInDb]:
        """Schema for the "contacts" domain."""
        return ContactInDb

    @property
    def repository(self) -> ContactsRepository:
        """Repository for the "contacts" domain."""
        return self._repository

    @repository.setter
    def repository(self, value: ContactsRepository):
        """Repository for the "contacts" domain."""
        self._repository = value

    def __init__(self, db: AsyncSession | None = None):
        """Initialize Contact Service."""
        self._repository = ContactsRepository(db=db)

    @staticmethod
    def _clean_email(email: str | EmailStr) -> str:
        """Return the one DB/write/lookup email identity form."""
        return str(email).strip().lower()

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Require self-describing E.164 rather than guessing a country."""
        result = PhoneNumberNormalizationService().parse_to_e164(phone)
        if not result.success or result.e164 is None:
            raise ContactIdentityInvalid("Phone number must be valid E.164.")
        return result.e164

    @classmethod
    def _normalize_identity(
        cls,
        *,
        organization_id: UUID,
        contact_id: UUID | None = None,
        external_id: str | None = None,
        email: str | EmailStr | None = None,
        phone: str | None = None,
    ) -> ContactIdentity:
        return ContactIdentity(
            organization_id=organization_id,
            contact_id=contact_id,
            external_id=external_id,
            email=cls._clean_email(email) if email is not None else None,
            phone=cls._clean_phone(phone) if phone is not None else None,
        )

    @classmethod
    def _normalize_create(cls, request: ContactCreateSchema) -> ContactCreateSchema:
        updates = {}
        if request.primary_email is not None:
            updates["primary_email"] = cls._clean_email(request.primary_email)
        if request.primary_phone is not None:
            updates["primary_phone"] = cls._clean_phone(request.primary_phone)
        return request.model_copy(update=updates)

    @classmethod
    def _normalize_update(cls, request: ContactUpdateSchema) -> ContactUpdateSchema:
        updates = {}
        supplied = request.model_fields_set
        if "primary_email" in supplied and request.primary_email is not None:
            updates["primary_email"] = cls._clean_email(request.primary_email)
        if "primary_phone" in supplied and request.primary_phone is not None:
            updates["primary_phone"] = cls._clean_phone(request.primary_phone)
        return request.model_copy(update=updates)

    async def _create_and_record(
        self,
        request: ContactCreateSchema,
        *,
        actor_kind: ContactActorKind,
        actor_id: UUID | None,
    ) -> ContactsModel:
        entity = await self.repository.create_(request)
        effective_actor_id = (
            entity.id if actor_kind is ContactActorKind.CONTACT else actor_id
        )
        changed_fields = tuple(
            field
            for field in (
                "external_id",
                "name",
                "primary_email",
                "primary_phone",
                "preferences",
            )
            if getattr(entity, field) is not None
        )
        await self._record_lifecycle_fact(
            entity,
            event_type="contact.created",
            changed_fields=changed_fields,
            actor_kind=actor_kind,
            actor_id=effective_actor_id,
        )
        return entity

    async def _record_lifecycle_fact(
        self,
        entity: ContactsModel,
        *,
        event_type: str,
        changed_fields: tuple[str, ...],
        actor_kind: ContactActorKind,
        actor_id: UUID | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        await DurableEventService(self.repository.db_session).file(
            envelope=DurableEventEnvelope(
                event_id=uuid4(),
                organization_id=entity.organization_id,
                subject_type=CONTACT_SUBJECT_TYPE,
                subject_id=entity.id,
                event_type=event_type,
                event_version=1,
                occurred_at=now,
                recorded_at=now,
                payload={
                    "actor_kind": actor_kind.value,
                    "actor_id": str(actor_id) if actor_id is not None else None,
                    "changed_fields": sorted(changed_fields),
                },
            ),
            consumer_names=(),
        )

    @staticmethod
    def _require_active(entity: ContactsModel) -> None:
        if entity.lifecycle != ContactLifecycle.ACTIVE.value:
            raise ContactDeletionPending("Contact deletion is pending.")

    async def create_(
        self,
        request: ContactCreateSchema,
        *,
        actor_kind: ContactActorKind = ContactActorKind.SYSTEM,
        actor_id: UUID | None = None,
    ) -> ContactInDb:
        """Create one contact and its content-free lifecycle fact atomically."""
        try:
            entity = await self._create_and_record(
                self._normalize_create(request),
                actor_kind=actor_kind,
                actor_id=actor_id,
            )
        except IntegrityError as error:
            raise ContactConflict("Contact identity already exists.") from error
        return self.orm_to_schema(entity)

    async def update_(
        self,
        request: ContactUpdateSchema,
        *,
        actor_kind: ContactActorKind = ContactActorKind.SYSTEM,
        actor_id: UUID | None = None,
    ) -> ContactInDb:
        """Patch maintained fields without making organization ownership mutable."""
        normalized = self._normalize_update(request)
        ref = ContactRef(
            organization_id=normalized.organization_id,
            contact_id=normalized.id,
        )
        entity = await self.repository.get_member_by_ref(ref, for_update=True)
        if entity is None:
            raise ContactNotFound("Contact not found")
        self._require_active(entity)

        changes = normalized.model_dump(
            exclude={"id", "organization_id"},
            exclude_unset=True,
        )
        changed_fields = tuple(
            field for field, value in changes.items() if value != getattr(entity, field)
        )
        if not changed_fields:
            return self.orm_to_schema(entity)

        try:
            entity = await self.repository.update_(normalized, contact=entity)
            await self._record_lifecycle_fact(
                entity,
                event_type="contact.updated",
                changed_fields=changed_fields,
                actor_kind=actor_kind,
                actor_id=actor_id,
            )
        except IntegrityError as error:
            raise ContactConflict("Contact identity already exists.") from error
        return self.orm_to_schema(entity)

    async def get_by_ref(self, ref: ContactRef) -> ContactInDb | None:
        """Resolve an active contact only through its tenant-bearing reference."""
        entity = await self.repository.get_by_ref(ref)
        return self.orm_to_schema(entity) if entity else None

    async def get_member_by_ref(self, ref: ContactRef) -> ContactInDb | None:
        """Read an owned contact for member lifecycle management."""
        entity = await self.repository.get_member_by_ref(ref)
        return self.orm_to_schema(entity) if entity else None

    async def require_active(
        self,
        ref: ContactRef,
        *,
        for_update: bool = False,
    ) -> ContactInDb:
        """Resolve one active contact, optionally serializing a new reference."""
        entity = await self.repository.get_member_by_ref(ref, for_update=for_update)
        if entity is None:
            raise ContactNotFound("Contact not found")
        self._require_active(entity)
        return self.orm_to_schema(entity)

    async def request_deletion(
        self,
        ref: ContactRef,
        *,
        actor_member_id: UUID,
    ) -> ContactInDb:
        """Fence a contact immediately; erasure remains asynchronous."""
        entity = await self.repository.get_member_by_ref(ref, for_update=True)
        if entity is None:
            raise ContactNotFound("Contact not found")
        if entity.lifecycle == ContactLifecycle.DELETION_PENDING.value:
            return self.orm_to_schema(entity)

        entity.lifecycle = ContactLifecycle.DELETION_PENDING.value
        entity.deletion_requested_at = datetime.now(timezone.utc)
        entity = await self.repository.save_(entity)
        await self._record_lifecycle_fact(
            entity,
            event_type="contact.deletion-requested",
            changed_fields=("lifecycle",),
            actor_kind=ContactActorKind.MEMBER,
            actor_id=actor_member_id,
        )
        return self.orm_to_schema(entity)

    async def _get_by_contact(
        self,
        organization_id: UUID,
        contact_kind: Literal["email", "phone"],
        contact: str,
    ) -> ContactInDb | None:
        """Get Contact by Contact Method."""
        entity = None
        if contact_kind == "email":
            entity = await self.repository.filter_one_(
                [
                    self.repository.model.organization_id == organization_id,
                    self.repository.model.primary_email == self._clean_email(contact),
                    self.repository.model.deleted.is_(False),
                    self.repository.model.lifecycle == ContactLifecycle.ACTIVE.value,
                ]
            )
        elif contact_kind == "phone":
            normalized_phone = self._clean_phone(contact)
            entity = await self.repository.filter_one_(
                [
                    self.repository.model.organization_id == organization_id,
                    self.repository.model.primary_phone == normalized_phone,
                    self.repository.model.deleted.is_(False),
                    self.repository.model.lifecycle == ContactLifecycle.ACTIVE.value,
                ]
            )
        return self.orm_to_schema(entity) if entity else None

    async def get_by_email(
        self, organization_id: UUID, email: str
    ) -> ContactInDb | None:
        """Get Contact by Email."""
        return await self._get_by_contact(
            organization_id=organization_id, contact_kind="email", contact=email
        )

    async def get_by_phone(
        self, organization_id: UUID, phone: str
    ) -> ContactInDb | None:
        """Get Contact by Phone."""
        return await self._get_by_contact(
            organization_id=organization_id, contact_kind="phone", contact=phone
        )

    async def resolve_identity(
        self,
        *,
        organization_id: UUID,
        email: str | EmailStr | None = None,
        phone: str | None = None,
        external_id: str | None = None,
        contact_id: UUID | None = None,
    ) -> ContactResolution:
        """Resolve all supplied identifiers, then select one priority winner."""
        identity = self._normalize_identity(
            organization_id=organization_id,
            contact_id=contact_id,
            external_id=external_id,
            email=email,
            phone=phone,
        )
        matches = await self.repository.find_identity_matches(
            organization_id=identity.organization_id,
            contact_id=identity.contact_id,
            external_id=identity.external_id,
            email=identity.email,
            phone=identity.phone,
        )
        return self._resolution(identity, matches)

    async def resolve_or_create(
        self,
        request: ContactCreateSchema,
        *,
        actor_kind: ContactActorKind = ContactActorKind.CONTACT,
        actor_id: UUID | None = None,
    ) -> ContactResolution:
        """Deduplicate one identify command and recover a concurrent insert."""
        normalized = self._normalize_create(request)
        resolution = await self.resolve_identity(
            organization_id=normalized.organization_id,
            external_id=normalized.external_id,
            email=normalized.primary_email,
            phone=normalized.primary_phone,
        )
        if resolution.contact is not None:
            return resolution

        try:
            async with self.repository.db_session.begin_nested():
                entity = await self._create_and_record(
                    normalized,
                    actor_kind=actor_kind,
                    actor_id=actor_id,
                )
                contact = self.orm_to_schema(entity)
        except IntegrityError:
            raced = await self.resolve_identity(
                organization_id=normalized.organization_id,
                external_id=normalized.external_id,
                email=normalized.primary_email,
                phone=normalized.primary_phone,
            )
            if raced.contact is not None:
                return raced
            raise
        return ContactResolution(
            contact=contact,
            matched_by=None,
            created=True,
        )

    def _resolution(
        self,
        identity: ContactIdentity,
        matches: list[ContactsModel],
    ) -> ContactResolution:
        by_kind = {
            ContactIdentifierKind.CONTACT_ID: identity.contact_id,
            ContactIdentifierKind.EXTERNAL_ID: identity.external_id,
            ContactIdentifierKind.EMAIL: identity.email,
            ContactIdentifierKind.PHONE: identity.phone,
        }
        attributes = {
            ContactIdentifierKind.CONTACT_ID: "id",
            ContactIdentifierKind.EXTERNAL_ID: "external_id",
            ContactIdentifierKind.EMAIL: "primary_email",
            ContactIdentifierKind.PHONE: "primary_phone",
        }
        matched_rows = {}
        for kind, value in by_kind.items():
            if value is None:
                continue
            matched_rows[kind] = next(
                (row for row in matches if getattr(row, attributes[kind]) == value),
                None,
            )

        winner_kind = next(
            (kind for kind, row in matched_rows.items() if row is not None),
            None,
        )
        if winner_kind is None:
            return ContactResolution(contact=None, matched_by=None)
        winner = matched_rows[winner_kind]
        assert winner is not None
        self._require_active(winner)
        conflicts = tuple(
            kind
            for kind, row in matched_rows.items()
            if row is not None and row.id != winner.id
        )
        return ContactResolution(
            contact=self.orm_to_schema(winner),
            matched_by=winner_kind,
            conflicting_identifiers=conflicts,
        )

    async def list_by_conversation(self, conversation_id: UUID) -> list[ContactInDb]:
        from eylo.modules.conversations.constants import DELETED_CONTACT_ENTITY_ID
        from eylo.modules.conversations.services.participants import (
            ConversationParticipantService,
        )

        participants = await ConversationParticipantService().list_by_conversation(
            conversation_id
        )
        contacts = ConversationParticipantService.filter_contact_participants(
            participants
        )
        contact_ids = [
            UUID(p.entity_id)
            for p in contacts
            if p.entity_id != DELETED_CONTACT_ENTITY_ID
        ]
        if not contact_ids:
            return []

        return self.orm_to_schema_list(
            await self.repository.filter_(
                filters=[
                    self.repository.model.id.in_(contact_ids),
                ]
            )
        )

    async def list_by_ids(
        self, contact_ids: list[UUID], organization_id: UUID
    ) -> list[ContactInDb]:
        """List Contacts by IDs."""
        if not contact_ids:
            return []

        return self.orm_to_schema_list(
            await self.repository.list_by_ids(contact_ids, organization_id)
        )

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        query: ContactListQuery | None = None,
    ) -> list[ContactInDb]:
        """List owned contacts with server-side search, filtering, and sorting."""
        query = query or ContactListQuery()
        model = self.repository.model
        sort_column = {
            ContactSortField.NAME: model.name,
            ContactSortField.PRIMARY_EMAIL: model.primary_email,
            ContactSortField.PRIMARY_PHONE: model.primary_phone,
            ContactSortField.CREATED_AT: model.created_at,
            ContactSortField.UPDATED_AT: model.updated_at,
        }[query.sort_by]
        order = (
            sort_column.asc().nulls_last()
            if query.sort_direction is ContactSortDirection.ASC
            else sort_column.desc().nulls_last()
        )

        return self.orm_to_schema_list(
            await self.repository.filter_(
                self._collection_filters(organization_id, query),
                limit=limit,
                offset=offset,
                order_by=[order, model.id.desc()],
            )
        )

    async def count_by_organization(
        self,
        organization_id: UUID,
        query: ContactListQuery | None = None,
    ) -> int:
        """Count the same filtered collection returned by the list query."""
        query = query or ContactListQuery()
        return await self.repository.count_(
            filters=self._collection_filters(organization_id, query)
        )

    def _collection_filters(
        self,
        organization_id: UUID,
        query: ContactListQuery,
    ) -> list:
        """Build the one filter set shared by collection rows and totals."""
        model = self.repository.model
        _filters = [
            model.organization_id == organization_id,
            model.deleted.is_(False),
        ]

        if query.contact_ids:
            _filters.append(model.id.in_(query.contact_ids))

        if query.search:
            term = f"%{query.search}%"
            _filters.append(
                or_(
                    model.name.ilike(term),
                    model.primary_email.ilike(term),
                    model.primary_phone.ilike(term),
                    model.external_id.ilike(term),
                )
            )
        if query.lifecycles:
            _filters.append(
                model.lifecycle.in_(
                    tuple(lifecycle.value for lifecycle in query.lifecycles)
                )
            )
        return _filters
