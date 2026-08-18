"""API schemas for explicit organization-owned sandbox configs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from eylo.common.schemas import EyloBaseApiSchema

__all__ = [
    "SandboxConfigCreate",
    "SandboxConfigResponse",
    "SandboxConfigSettings",
    "SandboxConfigUpdate",
    "SandboxConfigVerificationResponse",
]


class SandboxConfigSettings(EyloBaseApiSchema):
    """Docker V1 fields; every security/resource choice is explicit."""

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint: str = Field(min_length=8, max_length=512)
    image: str = Field(min_length=1, max_length=512)
    memory_mb: int = Field(ge=64, le=16384)
    cpu_cores: float = Field(gt=0, le=8)
    disk_mb: int = Field(ge=64, le=16384)
    pids: int = Field(ge=8, le=4096)
    ttl_seconds: int = Field(ge=60, le=86400)
    command_timeout_seconds: int = Field(ge=1, le=3600)
    max_output_bytes: int = Field(ge=1024, le=10 * 1024 * 1024)
    max_sessions: int = Field(ge=1, le=100)
    network: Literal[False]


class SandboxConfigCreate(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["docker"]
    name: str = Field(min_length=1)
    config: SandboxConfigSettings
    secrets: dict[str, str] = Field(default_factory=dict, max_length=0)


class SandboxConfigUpdate(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    config: SandboxConfigSettings | None = None
    secrets: dict[str, str | None] | None = Field(default=None, max_length=0)
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class SandboxConfigVerificationResponse(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    verified: bool = True
    provider: str
    revision: int = Field(gt=0)
    verified_at: datetime


class SandboxConfigResponse(EyloBaseApiSchema):
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
    config: SandboxConfigSettings
    secrets: dict[str, str]
