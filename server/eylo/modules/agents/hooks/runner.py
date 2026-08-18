"""Invoke run- and Agent-scoped lifecycle hooks without controlling the loop."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from eylo.common.contracts.llm_response import LLMResponse
from eylo.modules.agents.hooks.types import (
    AgentHooks,
    AgentInDb,
    HookContext,
    RunHooks,
)
from eylo.modules.conversations.schemas.messages import MessageInDb
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformToolResult

logger = logging.getLogger(__name__)


class HookRunner:
    """Manages hook registration and dispatch with error isolation."""

    def __init__(self) -> None:
        self._run_hooks: list[RunHooks] = []
        self._agent_hooks_resolver: Optional[
            Callable[[AgentInDb], Optional[AgentHooks]]
        ] = None

    def add_run_hooks(self, hooks: RunHooks) -> None:
        """Register run-level hooks. Called in registration order."""
        self._run_hooks.append(hooks)

    def set_agent_hooks_resolver(
        self,
        resolver: Callable[[AgentInDb], Optional[AgentHooks]],
    ) -> None:
        """Set a function that resolves AgentHooks for a given agent.
        Returns None if the agent has no hooks configured.
        """
        self._agent_hooks_resolver = resolver

    def _get_agent_hooks(self, agent: AgentInDb) -> Optional[AgentHooks]:
        """Resolve AgentHooks for the given agent."""
        if self._agent_hooks_resolver is None:
            return None
        try:
            return self._agent_hooks_resolver(agent)
        except Exception as error:
            logger.error(
                "Failed to resolve AgentHooks agent=%s error_type=%s",
                agent.id,
                type(error).__name__,
            )
            return None

    async def _safe_call(self, hook_name: str, coro) -> None:
        """Call a hook coroutine with error isolation."""
        try:
            await coro
        except Exception as error:
            logger.error(
                "Hook failed hook=%s error_type=%s; continuing",
                hook_name,
                type(error).__name__,
            )

    # --- Lifecycle dispatch methods ---

    async def on_agent_start(self, context: HookContext, agent: AgentInDb) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_agent_start",
                hook.on_agent_start(context, agent),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_start",
                agent_hooks.on_start(context, agent),
            )

    async def on_agent_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        output: MessageInDb,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_agent_end",
                hook.on_agent_end(context, agent, output),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_end",
                agent_hooks.on_end(context, agent, output),
            )

    async def on_agent_error(
        self,
        context: HookContext,
        agent: AgentInDb,
        error: Exception,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_agent_error",
                hook.on_agent_error(context, agent, error),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_error",
                agent_hooks.on_error(context, agent, error),
            )

    async def on_llm_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        system_prompt: Optional[str],
        messages: list[MessageInDb],
        tools: list[ToolInDb],
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_llm_start",
                hook.on_llm_start(context, agent, system_prompt, messages, tools),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_llm_start",
                agent_hooks.on_llm_start(
                    context, agent, system_prompt, messages, tools
                ),
            )

    async def on_llm_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        response: LLMResponse,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_llm_end",
                hook.on_llm_end(context, agent, response),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_llm_end",
                agent_hooks.on_llm_end(context, agent, response),
            )

    async def on_tool_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        tool_input: dict,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_tool_start",
                hook.on_tool_start(context, agent, tool, tool_input, tool_use_message),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_tool_start",
                agent_hooks.on_tool_start(
                    context, agent, tool, tool_input, tool_use_message
                ),
            )

    async def on_tool_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        result: PlatformToolResult,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_tool_end",
                hook.on_tool_end(context, agent, tool, result, tool_use_message),
            )
        agent_hooks = self._get_agent_hooks(agent)
        if agent_hooks:
            await self._safe_call(
                f"{agent_hooks.__class__.__name__}.on_tool_end",
                agent_hooks.on_tool_end(context, agent, tool, result, tool_use_message),
            )

    async def on_handoff(
        self,
        context: HookContext,
        from_agent: AgentInDb,
        to_agent: AgentInDb,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_handoff",
                hook.on_handoff(context, from_agent, to_agent),
            )
        # Fire AgentHooks for both source and target agents
        from_hooks = self._get_agent_hooks(from_agent)
        if from_hooks:
            await self._safe_call(
                f"{from_hooks.__class__.__name__}.on_handoff (source)",
                from_hooks.on_handoff(context, from_agent, to_agent),
            )
        to_hooks = self._get_agent_hooks(to_agent)
        if to_hooks:
            await self._safe_call(
                f"{to_hooks.__class__.__name__}.on_handoff (target)",
                to_hooks.on_handoff(context, from_agent, to_agent),
            )

    async def on_turn_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        turn: int,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_turn_start",
                hook.on_turn_start(context, agent, turn),
            )

    async def on_turn_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        turn: int,
    ) -> None:
        for hook in self._run_hooks:
            await self._safe_call(
                f"{hook.__class__.__name__}.on_turn_end",
                hook.on_turn_end(context, agent, turn),
            )
