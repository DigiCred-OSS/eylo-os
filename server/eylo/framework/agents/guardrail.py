"""Guardrail contracts for framework runs and tool calls."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject

if TYPE_CHECKING:
    from .context import RunContext, RunInput
    from .result import RunResult
    from .tool import ToolCall, ToolResult


class GuardrailStage(str, Enum):
    """Where a guardrail runs."""

    INPUT = "input"
    OUTPUT = "output"
    TOOL_INPUT = "tool_input"
    TOOL_OUTPUT = "tool_output"


class GuardrailSpec(FrozenFrameworkModel):
    """Configuration for a guardrail attached to a run or tool."""

    name: str
    stage: GuardrailStage
    description: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class GuardrailResult(FrozenFrameworkModel):
    """Structured result from a guardrail check."""

    name: str
    stage: GuardrailStage
    tripwire_triggered: bool = False
    message: str | None = None
    output_info: JsonObject = Field(default_factory=dict)


class Guardrail(Protocol):
    """Protocol for guardrails in the framework path."""

    spec: GuardrailSpec

    async def check_input(
        self,
        context: RunContext,
        run_input: RunInput,
    ) -> GuardrailResult:
        """Validate LLM-visible input before a model call."""

    async def check_output(
        self,
        context: RunContext,
        result: RunResult,
    ) -> GuardrailResult:
        """Validate final output before completion."""

    async def check_tool_input(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> GuardrailResult:
        """Validate a proposed tool call before execution."""

    async def check_tool_output(
        self,
        context: RunContext,
        tool_result: ToolResult,
    ) -> GuardrailResult:
        """Validate a tool result before feeding it back to the model."""
