"""Define lifecycle hook context and run- or Agent-scoped callback contracts."""

from __future__ import annotations

import logging
import time
from typing import Optional
from uuid import UUID

from eylo.common.contracts.llm_response import LLMResponse
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.messages import MessageInDb
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformToolResult

logger = logging.getLogger(__name__)
PRE_LOOP_ITERATION = -1


class HookContext:
    """Read-only context available to all hook callbacks.

    Provides information about the current state of the agent run
    without giving hooks mutable access to the loop's internals.

    Attributes:
        conversation_context: Full conversation state (messages, participants, agent, tools).
        request_id: UUID of the current user request being processed.
        user_message: The user message that triggered this agent run.
        iteration: Current ReAct loop iteration (1-based). -1 before loop starts.
        elapsed_seconds: Wall-clock seconds since the run started.

    """

    __slots__ = (
        "conversation_context",
        "request_id",
        "user_message",
        "_start_time",
        "iteration",
    )

    def __init__(
        self,
        conversation_context: ConversationContext,
        request_id: UUID,
        user_message: MessageInDb,
    ) -> None:
        self.conversation_context = conversation_context
        self.request_id = request_id
        self.user_message = user_message
        self._start_time = time.monotonic()
        self.iteration: int = PRE_LOOP_ITERATION

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def update_context(self, ctx: ConversationContext) -> None:
        """Update the conversation context (called by the loop after context rebuild)."""
        self.conversation_context = ctx


class RunHooks:
    """Run-level lifecycle callbacks isolated from Agent-loop control flow.

    Implementations may persist lifecycle projections, but must not mutate the
    loop's internal state. Hook failures are logged without changing the run
    result.
    """

    async def on_agent_start(
        self,
        context: HookContext,
        agent: AgentInDb,
    ) -> None:
        """Called before the agent begins processing. Also called after handoff
        when a new agent becomes active.

        Args:
            context: Read-only hook context with conversation state.
            agent: The agent that is about to begin processing.

        """
        pass

    async def on_agent_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        output: MessageInDb,
    ) -> None:
        """Called when the agent produces a final output (text response stored in DB).

        Args:
            context: Read-only hook context.
            agent: The agent that produced the output.
            output: The final ASSISTANT message stored in the database.

        """
        pass

    async def on_agent_error(
        self,
        context: HookContext,
        agent: AgentInDb,
        error: Exception,
    ) -> None:
        """Called when the agent run fails with an unhandled error.

        Args:
            context: Read-only hook context.
            agent: The agent that was active when the error occurred.
            error: The exception that caused the failure.

        """
        pass

    async def on_llm_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        system_prompt: Optional[str],
        messages: list[MessageInDb],
        tools: list[ToolInDb],
    ) -> None:
        """Called just before invoking the LLM.

        Args:
            context: Read-only hook context.
            agent: The agent making the LLM call.
            system_prompt: The system prompt sent to the LLM (may be None).
            messages: The message history sent to the LLM.
            tools: The tools available to the LLM for this call.

        """
        pass

    async def on_llm_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        response: LLMResponse,
    ) -> None:
        """Called immediately after the LLM call returns.

        Args:
            context: Read-only hook context.
            agent: The agent that made the LLM call.
            response: The raw LLM response.

        """
        pass

    async def on_tool_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        tool_input: dict,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Called immediately before a tool is invoked.

        Args:
            context: Read-only hook context.
            agent: The agent that requested the tool call.
            tool: The tool about to be executed.
            tool_input: The input parameters for the tool call.
            tool_use_message: The tool_use MessageInDb (for event broadcasting).

        """
        pass

    async def on_tool_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        result: PlatformToolResult,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Called immediately after a tool returns.

        Args:
            context: Read-only hook context.
            agent: The agent that requested the tool call.
            tool: The tool that was executed.
            result: The tool execution result (may indicate error via is_error).
            tool_use_message: The tool_use MessageInDb (for event broadcasting).

        """
        pass

    async def on_handoff(
        self,
        context: HookContext,
        from_agent: AgentInDb,
        to_agent: AgentInDb,
    ) -> None:
        """Called when a handoff occurs between agents.

        Args:
            context: Read-only hook context.
            from_agent: The agent handing off control.
            to_agent: The agent receiving control.

        """
        pass

    async def on_turn_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        turn: int,
    ) -> None:
        """Called at the beginning of each ReAct loop turn.

        Args:
            context: Read-only hook context.
            agent: The agent active for this turn.
            turn: The 1-based turn number.

        """
        pass

    async def on_turn_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        turn: int,
    ) -> None:
        """Called at the end of each ReAct loop turn, after tool execution
        and context rebuild (if any).

        Args:
            context: Read-only hook context.
            agent: The agent active for this turn.
            turn: The 1-based turn number.

        """
        pass


class AgentHooks:
    """Agent-level lifecycle hooks. Fire only when the specific agent they
    are attached to is the active agent. Set on agent configuration.

    Same interface as RunHooks but scoped to a single agent.
    Subclass and override the methods you need.
    """

    async def on_start(
        self,
        context: HookContext,
        agent: AgentInDb,
    ) -> None:
        """Called before this agent begins processing. Called each time the
        running agent changes to this agent (e.g., after handoff).

        Args:
            context: Read-only hook context.
            agent: This agent instance.

        """
        pass

    async def on_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        output: MessageInDb,
    ) -> None:
        """Called when this agent produces a final output.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            output: The final ASSISTANT message.

        """
        pass

    async def on_error(
        self,
        context: HookContext,
        agent: AgentInDb,
        error: Exception,
    ) -> None:
        """Called when this agent fails with an error.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            error: The exception that caused the failure.

        """
        pass

    async def on_llm_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        system_prompt: Optional[str],
        messages: list[MessageInDb],
        tools: list[ToolInDb],
    ) -> None:
        """Called just before this agent invokes the LLM.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            system_prompt: The system prompt.
            messages: The message history.
            tools: Available tools.

        """
        pass

    async def on_llm_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        response: LLMResponse,
    ) -> None:
        """Called immediately after this agent receives the LLM response.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            response: The raw LLM response.

        """
        pass

    async def on_tool_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        tool_input: dict,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Called immediately before this agent invokes a tool.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            tool: The tool about to be executed.
            tool_input: Input parameters for the tool.
            tool_use_message: The tool_use MessageInDb (for event broadcasting).

        """
        pass

    async def on_tool_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        result: PlatformToolResult,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Called immediately after a tool returns for this agent.

        Args:
            context: Read-only hook context.
            agent: This agent instance.
            tool: The tool that was executed.
            result: The tool execution result.
            tool_use_message: The tool_use MessageInDb (for event broadcasting).

        """
        pass

    async def on_handoff(
        self,
        context: HookContext,
        from_agent: AgentInDb,
        to_agent: AgentInDb,
    ) -> None:
        """Called when this agent is involved in a handoff (either as source or target).

        Args:
            context: Read-only hook context.
            from_agent: The agent handing off control.
            to_agent: The agent receiving control.

        """
        pass
