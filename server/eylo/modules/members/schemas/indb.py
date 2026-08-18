"""Data Transfer Objects (DTOs) for platform users."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from eylo.common.schemas import EyloBaseOrganizationModelSchema
from eylo.modules.members.models import MemberStatus
from eylo.modules.organizations.schemas import OrganizationModelSchema


class MemberModelSchema(EyloBaseOrganizationModelSchema):
    organization_id: UUID = Field(..., description="Organization ID")
    email: EmailStr = Field(..., description="User's email address")
    name: str = Field(..., description="User's full name")
    status: MemberStatus = Field(
        default=MemberStatus.ACTIVE, description="User's status in the organization"
    )
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    password: str = Field(None, description="User's password")
    organization: Optional[OrganizationModelSchema] = Field(
        None, description="User's organization"
    )


class MemberCreateSchema(BaseModel):
    organization_id: UUID = Field(..., description="Organization ID")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class MemberInDb(MemberModelSchema):
    model_config = ConfigDict(from_attributes=True)
