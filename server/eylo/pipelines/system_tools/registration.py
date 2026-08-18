"""Explicit registration of pipeline-backed tools under stable public slugs."""

from eylo.common.contracts.provider_config import Capability
from eylo.common.contracts.tool_availability import ToolRequirements, ToolRuntimeFact
from eylo.modules.tools.services.tool_register import system_tools_registry
from eylo.pipelines.system_tools.issue_visitor_chat_link import issue_chat_link
from eylo.pipelines.system_tools.knowledgebase_tools import (
    kb_query,
    kb_write,
    kb_write_destinations,
)
from eylo.pipelines.system_tools.memory_tools import (
    memory_forget,
    memory_recall,
    memory_refresh,
    memory_remember,
)
from eylo.pipelines.system_tools.sandbox_tools import (
    sandbox_exec,
    sandbox_read,
    sandbox_write,
)
from eylo.pipelines.system_tools.spawn_task_fnf import spawn_task_fnf
from eylo.pipelines.system_tools.telephony_tools import (
    dial_keypad,
    end_call,
    place_call,
    schedule_call,
    transfer_call,
)

_NO_REQUIREMENTS = ToolRequirements()
_MEMORY_REQUIREMENTS = ToolRequirements(
    agent_capabilities=frozenset({Capability.MEMORY}),
)
_SANDBOX_REQUIREMENTS = ToolRequirements(
    agent_capabilities=frozenset({Capability.SANDBOX}),
    runtime_facts=frozenset({ToolRuntimeFact.AGENT_RUN}),
)
_ACTIVE_CALL_REQUIREMENTS = ToolRequirements(
    runtime_facts=frozenset({ToolRuntimeFact.ACTIVE_CALL}),
)
_ACTIVE_VOICE_SESSION_REQUIREMENTS = ToolRequirements(
    runtime_facts=frozenset({ToolRuntimeFact.ACTIVE_VOICE_SESSION}),
)
_OUTBOUND_CALL_REQUIREMENTS = ToolRequirements(
    organization_capabilities=frozenset({Capability.TELEPHONY}),
    agent_capabilities=frozenset({Capability.TELEPHONY}),
)
_PLACE_CALL_REQUIREMENTS = ToolRequirements(
    organization_capabilities=_OUTBOUND_CALL_REQUIREMENTS.organization_capabilities,
    agent_capabilities=_OUTBOUND_CALL_REQUIREMENTS.agent_capabilities,
    runtime_facts=frozenset({ToolRuntimeFact.DURABLE_EXECUTION}),
)

_PIPELINE_SYSTEM_TOOLS = (
    ("dial_keypad", dial_keypad, _ACTIVE_CALL_REQUIREMENTS, Capability.TELEPHONY),
    ("end_call", end_call, _ACTIVE_VOICE_SESSION_REQUIREMENTS, None),
    ("issue_chat_link", issue_chat_link, _NO_REQUIREMENTS, None),
    ("kb_query", kb_query, _NO_REQUIREMENTS, None),
    ("kb_write", kb_write, _NO_REQUIREMENTS, None),
    ("kb_write_destinations", kb_write_destinations, _NO_REQUIREMENTS, None),
    ("memory_forget", memory_forget, _MEMORY_REQUIREMENTS, Capability.MEMORY),
    ("memory_recall", memory_recall, _MEMORY_REQUIREMENTS, Capability.MEMORY),
    ("memory_refresh", memory_refresh, _MEMORY_REQUIREMENTS, Capability.MEMORY),
    ("memory_remember", memory_remember, _MEMORY_REQUIREMENTS, Capability.MEMORY),
    ("place_call", place_call, _PLACE_CALL_REQUIREMENTS, Capability.TELEPHONY),
    ("sandbox_exec", sandbox_exec, _SANDBOX_REQUIREMENTS, Capability.SANDBOX),
    ("sandbox_read", sandbox_read, _SANDBOX_REQUIREMENTS, Capability.SANDBOX),
    ("sandbox_write", sandbox_write, _SANDBOX_REQUIREMENTS, Capability.SANDBOX),
    ("schedule_call", schedule_call, _OUTBOUND_CALL_REQUIREMENTS, Capability.TELEPHONY),
    ("spawn_task_fnf", spawn_task_fnf, _NO_REQUIREMENTS, None),
    ("transfer_call", transfer_call, _ACTIVE_CALL_REQUIREMENTS, Capability.TELEPHONY),
)


def register_pipeline_system_tools() -> None:
    """Register every pipeline tool once without directory scanning."""
    for tool_name, tool_func, requirements, provider_capability in _PIPELINE_SYSTEM_TOOLS:
        system_tools_registry.register_tool(
            tool_name,
            tool_func,
            requirements=requirements,
            provider_capability=provider_capability,
        )


def pipeline_system_tool_names() -> tuple[str, ...]:
    """Return the frozen tool-name manifest used by startup verification."""
    return tuple(name for name, _, _, _ in _PIPELINE_SYSTEM_TOOLS)


__all__ = ["pipeline_system_tool_names", "register_pipeline_system_tools"]
