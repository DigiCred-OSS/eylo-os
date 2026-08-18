"""Data contracts for the `contacts` domain."""

from typing import List, Optional

from pydantic import ConfigDict, EmailStr, Field

from eylo.common.schemas import (
    EyloBaseRequestSchema,
    EyloBaseResponseSchema,
    PaginatedResponseSchema,
)

from .indb import ContactInDb


class ContactCreateRequestSchema(EyloBaseRequestSchema):
    """Member-private contact creation payload.

    The authenticated member owns the organization boundary. A caller cannot
    select it in the request body.
    """

    model_config = ConfigDict(extra="forbid")

    external_id: Optional[str] = None
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    preferences: Optional[dict[str, str]] = Field(default_factory=dict)


class ContactPatchRequestSchema(EyloBaseRequestSchema):
    """Patch only maintained contact fields; omission and null are distinct."""

    model_config = ConfigDict(extra="forbid")

    external_id: Optional[str] = None
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    preferences: Optional[dict[str, str]] = None


class ContactApiResponseSchema(ContactInDb, EyloBaseResponseSchema):
    pass


# ====================== Response Models ======================


class ContactsPaginated(PaginatedResponseSchema):
    """Paginated list of Contact."""

    data: List[ContactApiResponseSchema]
