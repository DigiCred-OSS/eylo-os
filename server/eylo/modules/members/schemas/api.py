"""Data contracts for the `members` domain."""

import datetime
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import EmailStr, Field

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseRequestSchema,
    PaginatedResponseSchema,
)
from eylo.modules.members.models import MemberStatus


class MemberApiResponseSchema(EyloBaseApiSchema):
    id: UUID = Field(..., description="Member ID")
    organization_id: UUID = Field(..., description="Organization ID")
    email: EmailStr = Field(..., description="User's email address")
    name: str = Field(..., description="User's full name")
    status: MemberStatus = Field(
        default=MemberStatus.ACTIVE, description="User's status in the organization"
    )
    last_login: Optional[datetime.datetime] = Field(
        None, description="Last login timestamp"
    )
    created_at: datetime.datetime = Field(
        ..., description="Timestamp when the user was created"
    )


class MemberUpdateRequestSchema(EyloBaseRequestSchema):
    """Schema for updating an existing platform user."""

    name: Optional[str] = Field(None, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    deleted: Optional[bool] = Field(
        None, description="Whether the user account is active"
    )
    password: Optional[str] = Field(None, min_length=8, description="User's password")


class MemberRegisterSchema(EyloBaseRequestSchema):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class MemberFilterSchema(EyloBaseApiSchema):
    member_ids: Annotated[Optional[list[UUID]], Field(None, max_length=100)] = None


class MembersPaginated(PaginatedResponseSchema):
    """Paginated list of members."""

    data: List[MemberApiResponseSchema]
