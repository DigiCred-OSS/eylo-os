"""Data contracts for the `tools` domain."""

from datetime import datetime
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_snake
from pydantic.json_schema import SkipJsonSchema

from eylo.common.revisions import RevisionAvailability
from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.tools.models import ToolKind
from eylo.modules.tools.schemas.platform import PlatformTool, PlatformToolInputSchema
from eylo.modules.tools.services.tool_register import (
    local_tools_registry,
    system_tools_registry,
)

from .indb import ToolCreateSchema, ToolInDb, ToolUpdateSchema


class ToolFilterSchema(EyloBaseApiSchema):
    tool_ids: Annotated[Optional[list[UUID]], Field(None, max_length=100)] = None


class PlatformToolInputApiSchema(PlatformToolInputSchema, EyloBaseApiSchema):
    """Platform tool input schema with camelCase aliases for API."""

    pass


class PlatformToolApiSchema(PlatformTool, EyloBaseApiSchema):
    """Platform-native tool schema for API requests/responses."""

    input_schema: PlatformToolInputApiSchema = Field(
        ..., description="JSON Schema defining the tool's input parameters"
    )


def _convert_nested_dict_keys_to_snake_case(
    values: dict[str, Any], key: str
) -> dict[str, Any]:
    """Convert camelCase keys to snake_case for nested dicts.

    This utility handles the case where Pydantic's CamelModel alias configuration
    doesn't automatically apply during nested dict-to-model conversions.

    Args:
        values: The parent dict containing the nested dict
        key: The key (camelCase or snake_case) that contains the nested dict

    Returns:
        The modified values dict with converted nested keys

    """
    if not isinstance(values, dict):
        return values

    # Handle both camelCase and snake_case versions of the key
    # (CamelModel may have already converted the parent key)
    camel_key = key
    snake_key = to_snake(key)

    nested_key = None
    if camel_key in values:
        nested_key = camel_key
    elif snake_key in values:
        nested_key = snake_key

    if nested_key and values[nested_key]:
        nested_dict = values[nested_key]
        if isinstance(nested_dict, dict):
            # Convert all camelCase keys to snake_case
            values[nested_key] = {to_snake(k): v for k, v in nested_dict.items()}

    return values


def _validate_registered_tool(tool_name: str):
    if tool_name is None:
        raise ValueError("Tool name cannot be None.")
    if system_tools_registry.get_tool(tool_name) is not None:
        raise ValueError(f"Tool '{tool_name}' is part of system tools.")
    if local_tools_registry.get_tool(tool_name) is None:
        raise ValueError(f"Tool '{tool_name}' is not part of local tools.")
    return True


class ToolCreateRequestSchema(ToolCreateSchema, EyloBaseApiSchema):
    organization_id: SkipJsonSchema[UUID | None] = Field(default=None, exclude=True)
    llm_config: Optional[PlatformToolApiSchema] = Field(
        None, description="LLM schema for the tool"
    )
    executor_config: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Executor schema for the tool"
    )

    @model_validator(mode="before")
    def convert_nested_camelcase(cls, values):
        """Convert camelCase to snake_case for nested llmConfig fields."""
        return _convert_nested_dict_keys_to_snake_case(values, "llmConfig")

    @field_validator("llm_config", mode="before")
    @classmethod
    def validate_llm_config(cls, v):
        """Convert dict to PlatformToolApiSchema (overrides parent's PlatformTool conversion)."""
        if v is None or v == {}:
            return PlatformToolApiSchema(
                name="",
                description="",
                input_schema=PlatformToolInputApiSchema(
                    type="object", additional_properties=None
                ),
            )
        if isinstance(v, dict):
            return PlatformToolApiSchema.model_validate(v)
        return v

    @model_validator(mode="after")
    def validate_config_tool_kind(self):
        if self.kind == ToolKind.LOCAL and _validate_registered_tool(self.name):
            self.llm_config = local_tools_registry.get_llm_config(self.name)
            self.executor_config = {}
        return self

    @field_validator("kind", mode="after")
    def require_operator_managed_kind(cls, v: ToolKind) -> ToolKind:
        if v is not ToolKind.LOCAL:
            raise ValueError(
                "Only registered local tools can be created through this endpoint."
            )
        return v


class ToolUpdateRequestSchema(ToolUpdateSchema, EyloBaseApiSchema):
    llm_config: Optional[PlatformToolApiSchema] = Field(
        None, description="LLM schema for the tool"
    )
    executor_config: Optional[dict[str, Any]] = Field(
        None, description="Executor schema for the tool"
    )

    @model_validator(mode="before")
    def convert_nested_camelcase(cls, values):
        """Convert camelCase to snake_case for nested llmConfig fields."""
        return _convert_nested_dict_keys_to_snake_case(values, "llmConfig")

    @field_validator("llm_config", mode="before")
    @classmethod
    def validate_llm_config(cls, v):
        """Convert dict to PlatformToolApiSchema (overrides parent's PlatformTool conversion)."""
        if v is None or v == {}:
            return None
        if isinstance(v, dict):
            return PlatformToolApiSchema.model_validate(v)
        return v

class ToolResponseSchema(ToolInDb, EyloBaseApiSchema):
    llm_config: Optional[PlatformToolApiSchema] = Field(
        None, description="LLM schema for the tool"
    )
    executor_config: Optional[dict[str, Any]] = Field(
        None, description="Executor schema for the tool"
    )

    @field_validator("llm_config", mode="before")
    @classmethod
    def validate_llm_config(cls, value):
        if isinstance(value, PlatformTool):
            value = value.model_dump(by_alias=True, exclude_none=True)
        if isinstance(value, dict):
            return PlatformToolApiSchema.model_validate(value)
        return value


class ToolListResponseSchema(EyloBaseApiSchema):
    items: list[ToolResponseSchema]


class ToolPublishRequestSchema(EyloBaseApiSchema):
    expected_draft_version: int = Field(..., gt=0)


class ToolRevokeRequestSchema(EyloBaseApiSchema):
    reason: str = Field(..., min_length=1, max_length=2_000)


class ToolRevisionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_id: UUID
    revision: int
    availability: RevisionAvailability
    published_at: datetime
    published_by: UUID | None
    revoked_at: datetime | None
    revoked_by: UUID | None
    revocation_reason: str | None
    cancellation_requested_at: datetime | None
