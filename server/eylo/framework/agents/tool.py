"""Tool contracts for framework-managed agent capabilities."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol

from pydantic import Field

from .common import FrameworkMetadata, FrozenFrameworkModel, JsonObject

if TYPE_CHECKING:
    from .context import RunContext


class ToolKind(str, Enum):
    """Framework-visible tool family."""

    SYSTEM = "system"
    LOCAL = "local"
    API = "api"
    SANDBOX = "sandbox"
    HANDOFF = "handoff"


class ToolExecutionMode(str, Enum):
    """How a tool call may be executed."""

    AUTO = "auto"
    REQUIRES_APPROVAL = "requires_approval"
    DISABLED = "disabled"


class ToolSpec(FrozenFrameworkModel):
    """Tool definition exposed to a model."""

    name: str
    description: str
    kind: ToolKind
    input_schema: JsonObject = Field(default_factory=dict)
    execution_mode: ToolExecutionMode = ToolExecutionMode.AUTO
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class ToolCall(FrozenFrameworkModel):
    """One model-requested tool invocation."""

    id: str
    name: str
    arguments: JsonObject = Field(default_factory=dict)
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class ToolResult(FrozenFrameworkModel):
    """Result returned by a tool invocation."""

    tool_call_id: str
    content: str | dict | list
    is_error: bool = False
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class ToolExecutor(Protocol):
    """Protocol for tool dispatch in the new framework path."""

    async def execute(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> ToolResult:
        """Execute one tool call and return its result."""
