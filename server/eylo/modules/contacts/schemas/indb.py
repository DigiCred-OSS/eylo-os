"""Data contracts for the `contacts` domain."""

import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from eylo.common.schemas import EyloBaseOrganizationModelSchema, EyloBaseSchema
from eylo.modules.contacts.domain import ContactLifecycle


class ContactRef(EyloBaseSchema):
    """Immutable tenant-bearing reference to one contact aggregate."""

    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    contact_id: UUID


class ContactsModelSchema(EyloBaseOrganizationModelSchema):
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    preferences: Optional[dict[str, str]] = Field(default_factory=dict)
    lifecycle: ContactLifecycle
    deletion_requested_at: Optional[datetime.datetime] = None


class ContactInDb(ContactsModelSchema):
    model_config = ConfigDict(from_attributes=True)


class ContactCreateSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    external_id: Optional[str] = None
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    preferences: Optional[dict[str, str]] = Field(default_factory=dict)


class ContactUpdateSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    external_id: Optional[str] = None
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    preferences: Optional[dict[str, str]] = None
