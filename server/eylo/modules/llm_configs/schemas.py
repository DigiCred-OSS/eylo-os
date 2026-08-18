"""Data contracts for the `llm_configs` domain."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.llm_configs.catalog import LLMModels


class LLMOverridesSchema(EyloBaseApiSchema):
    """Optional non-secret generation overrides stored on an agent."""

    model_config = ConfigDict(extra="forbid")

    model: LLMModels | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_k: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop_sequences: tuple[str, ...] | None = None


class LLMConfigCreate(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    name: str = Field(min_length=1)
    config: dict[str, object]
    secrets: dict[str, str] = Field(default_factory=dict)


class LLMConfigUpdate(EyloBaseApiSchema):
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


class LLMConfigVerificationResponse(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    verified: bool = True
    provider: str
    model: str
    revision: int = Field(gt=0)
    verified_at: datetime


class LLMConfigResponse(EyloBaseApiSchema):
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
