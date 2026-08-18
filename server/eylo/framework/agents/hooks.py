"""Lifecycle hook contracts for framework runs."""

from __future__ import annotations

from .agent import AgentSpec
from .context import RunContext, RunInput
from .model import ModelResponse
from .result import RunResult
from .tool import ToolCall, ToolResult


class RunHooks:
    """No-op lifecycle callbacks for framework runs."""

    async def on_run_start(self, context: RunContext) -> None:
        """Run started."""

    async def on_run_end(self, context: RunContext, result: RunResult) -> None:
        """Run completed or stopped."""

    async def on_agent_start(self, context: RunContext, agent: AgentSpec) -> None:
        """Agent became active."""

    async def on_llm_start(self, context: RunContext, run_input: RunInput) -> None:
        """Model call started."""

    async def on_llm_end(
        self,
        context: RunContext,
        response: ModelResponse,
    ) -> None:
        """Model call completed."""

    async def on_tool_start(self, context: RunContext, call: ToolCall) -> None:
        """Tool execution started."""

    async def on_tool_end(
        self,
        context: RunContext,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        """Tool execution completed."""

    async def on_handoff(
        self,
        context: RunContext,
        from_agent: AgentSpec,
        to_agent: AgentSpec,
    ) -> None:
        """Active agent changed."""

    async def on_error(self, context: RunContext, error: Exception) -> None:
        """Run-level error occurred."""
