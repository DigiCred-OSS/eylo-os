"""Data contracts for the `auth` domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, Field

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseModelSchema,
    EyloBaseRequestSchema,
    EyloBaseSchema,
)


class ApiKeyBase(EyloBaseSchema):
    """Base schema for API Key data."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="A label for the API Key.")
    is_active: bool = Field(True, description="Whether the key is active.")
    expires_at: Optional[datetime] = Field(
        None, description="Optional expiration date."
    )


class ApiKeyCreate(ApiKeyBase, EyloBaseRequestSchema):
    """Schema for creating a new API Key."""

    pass


class ApiKeyInDb(ApiKeyBase, EyloBaseModelSchema):
    """Schema representing an API Key as stored in the database."""

    organization_id: UUID
    key_prefix: str
    hashed_key: str
    last_used_at: Optional[datetime] = None
    usage_count: int = 0


class ApiKeyResponse(ApiKeyInDb, EyloBaseApiSchema):
    """Schema for API Key responses. Includes the raw key only during creation."""

    raw_key: Optional[str] = Field(
        None, description="The raw API key. Only returned once during creation."
    )
