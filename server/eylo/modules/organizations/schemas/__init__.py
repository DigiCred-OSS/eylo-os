"""Public exports for the `organizations` domain package."""

from pydantic import BaseModel, Field

from eylo.common.schemas import EyloBaseModelSchema


class OrganizationModelSchema(EyloBaseModelSchema):
    name: str = Field(..., max_length=100)


class OrganisationCreateSchema(BaseModel):
    name: str = Field(..., max_length=100)
