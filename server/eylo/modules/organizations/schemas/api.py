"""Data contracts for the `organizations` domain."""

from pydantic import Field

from eylo.common.schemas import EyloBaseResponseSchema


class OrganizationResponseSchema(EyloBaseResponseSchema):
    name: str = Field(..., description="User's full name")
