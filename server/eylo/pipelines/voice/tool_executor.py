"""Tool execution authority for raw-free live voice turns."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import NAMESPACE_URL, UUID, uuid5

from eylo.framework.agents.context import RunContext
from eylo.framework.agents.tool import ToolCall, ToolExecutor, ToolResult
from eylo.pipelines.conversation.tool_executor import (
    PlatformToolExecutor,
)
from eylo.pipelines.sandbox.tool_execution import SANDBOX_TOOL_SLUGS
from eylo.pipelines.voice.live_buffer import LiveVoiceBufferIdentity

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LiveVoiceToolCommandRef:
    """Content-free identity consumed by existing product tool adapters."""

    id: UUID


class LiveVoiceCommandStepContext:
    """Run one live command while its product DB row owns replay safety.

    Outbound tools prepare a deterministic DB attempt before calling ``step``.
    The attempt fences duplicate sends and records interrupted/unknown outcomes;
    this adapter intentionally does not checkpoint raw tool output elsewhere.
    """

    async def step(
        self,
        *,
        key: str,
        version: int,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        if not key.strip() or version <= 0:
            raise ValueError("Live voice command step identity is invalid.")
        return await operation()


class LiveVoiceToolExecutor:
    """Supply durable product-command identity without a raw TOOL_USE message."""

    def __init__(
        self,
        identity: LiveVoiceBufferIdentity,
        *,
        delegate: ToolExecutor | None = None,
    ) -> None:
        self._identity = identity
        self._delegate = delegate or PlatformToolExecutor()
        self._step_context = LiveVoiceCommandStepContext()

    def command_id(self, tool_call_id: str) -> UUID:
        """Return the stable content-free product owner for one model tool call."""
        return _command_id(self._identity, tool_call_id)

    async def execute(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> ToolResult:
        local_context = context.local_context
        if not isinstance(local_context, dict):
            raise ValueError("Live voice tool execution requires local context.")
        command_ref = LiveVoiceToolCommandRef(
            id=self.command_id(call.id),
        )
        tool_use_messages = local_context.setdefault("tool_use_messages", {})
        if not isinstance(tool_use_messages, dict):
            raise ValueError("Live voice tool command state is invalid.")
        tool_use_messages[call.id] = command_ref
        local_context["durable_context"] = self._step_context
        try:
            return await self._delegate.execute(context, call)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Live voice tool command failed error_type=%s",
                type(error).__name__,
            )
            return ToolResult(
                tool_call_id=call.id,
                content={
                    "kind": "tool_error",
                    "error": "tool_execution_failed",
                },
                is_error=True,
                metadata={"live_voice_command_failed": True},
            )


def without_live_sandbox_tools(tools):
    """Remove sandbox tools from the latency-sensitive live voice surface."""
    return tuple(tool for tool in tools if not _is_sandbox_tool(tool))


def without_live_sandbox_agent_tools(agent):
    """Return one framework agent spec with live-voice-safe tools only."""
    return agent.model_copy(update={"tools": without_live_sandbox_tools(agent.tools)})


def _is_sandbox_tool(tool) -> bool:
    slug = getattr(tool, "slug", None)
    if slug is None:
        metadata = getattr(tool, "metadata", None)
        if metadata is not None:
            slug = metadata.get("slug")
    return slug in SANDBOX_TOOL_SLUGS


def _command_id(identity: LiveVoiceBufferIdentity, tool_call_id: str) -> UUID:
    voice_authority = identity.voice_session_id or identity.session_id
    return uuid5(
        NAMESPACE_URL,
        "eylo:live-voice-tool:"
        f"{identity.organization_id}:{voice_authority}:{tool_call_id}",
    )


__all__ = [
    "LiveVoiceCommandStepContext",
    "LiveVoiceToolCommandRef",
    "LiveVoiceToolExecutor",
    "without_live_sandbox_agent_tools",
    "without_live_sandbox_tools",
]
