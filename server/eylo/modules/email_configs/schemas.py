"""API schemas for email configs."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from eylo.common.schemas import EyloBaseApiSchema

__all__ = [
    "EmailConfigCreate",
    "EmailConfigUpdate",
    "EmailConfigResponse",
    "EmailConfigVerificationResponse",
]


class EmailConfigCreate(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    name: str = Field(min_length=1)
    config: dict[str, object]
    secrets: dict[str, str] = Field(default_factory=dict)


class EmailConfigUpdate(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    config: dict[str, object] | None = None
    secrets: dict[str, str | None] | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class EmailConfigVerificationResponse(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    verified: bool = True
    provider: str
    revision: int = Field(gt=0)
    verified_at: datetime


class EmailConfigResponse(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider: str
    name: str
    revision: int = Field(gt=0)
    enabled: bool
    configured: bool
    verified: bool
    ready: bool
    verified_at: datetime | None
    config: dict[str, object]
    secrets: dict[str, str]
