"""Typed contact collection query owned by the contacts domain."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from eylo.modules.contacts.domain import ContactLifecycle


class ContactSortField(StrEnum):
    NAME = "name"
    PRIMARY_EMAIL = "primary_email"
    PRIMARY_PHONE = "primary_phone"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class ContactSortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class ContactListQuery:
    contact_ids: tuple[UUID, ...] = ()
    search: str | None = None
    lifecycles: tuple[ContactLifecycle, ...] = ()
    sort_by: ContactSortField = ContactSortField.UPDATED_AT
    sort_direction: ContactSortDirection = ContactSortDirection.DESC
