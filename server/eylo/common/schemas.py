"""Shared Pydantic schema bases and pagination contracts."""

import datetime
import logging
from enum import Enum
from typing import Generic, List, Optional, TypeVar
from uuid import UUID

import arrow
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, ConfigDict, Field, field_validator

from eylo.common.identifiers import normalize_uuid_like

T = TypeVar("T")

logger = logging.getLogger(__name__)


class EyloBaseSchema(BaseModel):
    """EyloBaseSchema behavior for the "common" platform."""

    @field_validator("*", mode="before")
    @classmethod
    def normalize_uuid_fields(cls, value):
        return normalize_uuid_like(value)


class EyloBaseApiSchema(CamelModel):
    """EyloBaseApiSchema behavior for the "common" platform."""

    @field_validator("*", mode="before")
    @classmethod
    def normalize_uuid_fields(cls, value):
        return normalize_uuid_like(value)


def _get_dt_now() -> datetime.datetime:
    return arrow.utcnow().datetime


class EyloBaseModelSchema(BaseModel):
    """EyloBaseModelSchema behavior for the "common" platform."""

    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_uuid_fields(cls, value):
        return normalize_uuid_like(value)

    id: UUID = Field(..., description="Auto-generated unique identifier")
    deleted: bool = Field(default=True, description="Whether the record is active")
    created_at: datetime.datetime = Field(
        default_factory=_get_dt_now, description="Record creation timestamp"
    )
    updated_at: datetime.datetime = Field(
        default_factory=_get_dt_now, description="Record last update timestamp"
    )


class EyloBaseOrganizationModelSchema(EyloBaseModelSchema):
    """EyloBaseOrganizationModelSchema behavior for the "common" platform."""

    external_id: Optional[str] = Field(None, description="External Service identifier")
    organization_id: Optional[UUID] = Field(
        None, description="The ID of the organization this record belongs to."
    )


class EyloBaseResponseSchema(EyloBaseApiSchema):
    """EyloBaseResponseSchema behavior for the "common" platform."""

    id: UUID = Field(..., description="Auto-generated unique identifier")
    deleted: bool = Field(default=True, description="Whether the record is active")
    created_at: datetime.datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime.datetime = Field(
        ..., description="Record last update timestamp"
    )
    external_id: Optional[str] = Field(None, description="External Service identifier")


class PaginationParams(EyloBaseApiSchema):
    """PaginationParams behavior for the "common" platform."""

    page: int = Field(default=1, ge=1, description="Page number, starting from 1")
    limit: int = Field(default=10, ge=1, le=100, description="Number of items per page")
    total: Optional[int] = Field(
        None,
        description="Total number of items available (optional for client-side use)",
    )

    def get_offset(self) -> int:
        """Get offset for the "common" platform."""
        return (self.page - 1) * self.limit


class EyloBaseRequestSchema(EyloBaseApiSchema):
    """EyloBaseRequestSchema behavior for the "common" platform."""

    pass


class BaseResponseStatus(str, Enum):
    """BaseResponseStatus behavior for the "common" platform."""

    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class BaseResponseSchema(EyloBaseApiSchema, Generic[T]):
    """BaseResponseSchema behavior for the "common" platform."""

    status: BaseResponseStatus
    data: Optional[T] = None
    message: Optional[str] = None


class PaginatedResponseSchema(PaginationParams, Generic[T]):
    """PaginatedResponseSchema behavior for the "common" platform."""

    data: List[T]
    has_more: Optional[bool] = False


# Utilities #
class CaseInSensitiveEnum(str, Enum):
    """CaseInSensitiveEnum behavior for the "common" platform."""

    @classmethod
    def _missing_(cls, value):
        """Missing for the "common" platform."""
        # Handle case where value is already an enum member
        if isinstance(value, cls):
            return value

        # Convert value to string if it isn't one already
        if not isinstance(value, str):
            value = str(value)

        # Try case-insensitive matching
        for member in cls:
            if str(member.value).lower() == value.lower():
                return member

        try:
            return cls[value.upper()]  # Try to access directly with uppercase
        except KeyError:
            try:
                return cls[value.lower()]  # Try to access directly with lowercase
            except KeyError:
                logger.warning("Invalid enum value enum=%s", cls.__name__)
                try:
                    # Creating a enum instance based on the value
                    # We need to use super() to avoid infinite recursion.
                    unknown_enum_val = super().__new__(cls, value)
                    unknown_enum_val._name_ = str(value)  # pylint: disable=protected-access
                    unknown_enum_val._value_ = value  # pylint: disable=protected-access
                    return unknown_enum_val
                except Exception as error:
                    logger.error(
                        "Unknown enum construction failed enum=%s error_type=%s",
                        cls.__name__,
                        type(error).__name__,
                    )
                    return None

    def __eq__(self, other):
        """Enable case-insensitive string comparison."""
        if isinstance(other, str):
            return str(self.value).lower() == other.lower()
        return super().__eq__(other)
