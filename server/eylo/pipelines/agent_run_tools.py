"""Content-free command identities for non-conversation AgentRun tools."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from eylo.framework.agents.tool import ToolCall


@dataclass(frozen=True, slots=True)
class AgentRunToolCommandRef:
    """Stable product owner used by durable tool adapters."""

    id: UUID


def bind_agent_run_tool_command(
    local_context: dict,
    *,
    call: ToolCall,
    command_id: UUID,
) -> None:
    """Bind a call to an already persisted canonical command row."""
    tool_use_messages = local_context.setdefault("tool_use_messages", {})
    if not isinstance(tool_use_messages, dict):
        raise ValueError("AgentRun tool command state is invalid.")
    tool_use_messages[call.id] = AgentRunToolCommandRef(id=command_id)


__all__ = [
    "AgentRunToolCommandRef",
    "bind_agent_run_tool_command",
]
