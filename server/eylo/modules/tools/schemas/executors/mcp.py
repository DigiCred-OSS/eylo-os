"""Published execution contract for one discovered MCP tool."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPToolEffect(str, Enum):
    """Server-declared effect semantics accepted by the MCP executor."""

    READ_ONLY = "read_only"
    IDEMPOTENT_MUTATION = "idempotent_mutation"
    UNSUPPORTED = "unsupported"


class MCPToolExecutorConfig(BaseModel):
    """Exact server-side tool identity and reviewed execution semantics."""

    mcp_tool_name: str = Field(min_length=1, max_length=128)
    effect: MCPToolEffect
    protocol_version: Literal["2025-06-18"] = MCP_PROTOCOL_VERSION

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def validate_mcp_tool_executor_config(config: object) -> MCPToolExecutorConfig:
    if not isinstance(config, Mapping):
        raise ValueError("MCP tool executor config must be an object.")
    try:
        return MCPToolExecutorConfig.model_validate(config)
    except ValidationError:
        raise ValueError("MCP tool executor config is invalid.") from None


__all__ = [
    "MCP_PROTOCOL_VERSION",
    "MCPToolEffect",
    "MCPToolExecutorConfig",
    "validate_mcp_tool_executor_config",
]
