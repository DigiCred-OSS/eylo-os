"""Provider-neutral availability contract for code-owned system tools.

An agent-tool grant answers *may this agent use this tool?*.  Requirements
answer *can this tool work in this execution?*.  Keeping those questions
separate lets one agent hold a precise mix of tools without pretending that a
configured provider makes every provider-backed tool usable everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from eylo.common.contracts.provider_config import Capability


class ToolRuntimeFact(str, Enum):
    """Execution facts that cannot be inferred from provider configuration."""

    ACTIVE_CALL = "active_call"
    ACTIVE_VOICE_SESSION = "active_voice_session"
    DURABLE_EXECUTION = "durable_execution"
    AGENT_RUN = "agent_run"
    WIDGET = "widget"


@dataclass(frozen=True, slots=True)
class ToolRequirements:
    """Code-owned requirements for one system tool."""

    organization_capabilities: frozenset[Capability] = field(
        default_factory=frozenset
    )
    agent_capabilities: frozenset[Capability] = field(default_factory=frozenset)
    runtime_facts: frozenset[ToolRuntimeFact] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ToolAvailabilityFacts:
    """Capabilities and runtime facts available to one agent execution."""

    organization_capabilities: frozenset[Capability] = field(
        default_factory=frozenset
    )
    agent_capabilities: frozenset[Capability] = field(default_factory=frozenset)
    runtime_facts: frozenset[ToolRuntimeFact] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class MissingToolRequirements:
    """Stable, machine-readable reasons a system tool is unavailable."""

    organization_capabilities: frozenset[Capability]
    agent_capabilities: frozenset[Capability]
    runtime_facts: frozenset[ToolRuntimeFact]

    @property
    def available(self) -> bool:
        return not (
            self.organization_capabilities
            or self.agent_capabilities
            or self.runtime_facts
        )


def missing_tool_requirements(
    requirements: ToolRequirements,
    facts: ToolAvailabilityFacts,
) -> MissingToolRequirements:
    """Return the exact unmet requirements without any infrastructure access."""
    return MissingToolRequirements(
        organization_capabilities=(
            requirements.organization_capabilities
            - facts.organization_capabilities
        ),
        agent_capabilities=(
            requirements.agent_capabilities - facts.agent_capabilities
        ),
        runtime_facts=requirements.runtime_facts - facts.runtime_facts,
    )


__all__ = [
    "MissingToolRequirements",
    "ToolAvailabilityFacts",
    "ToolRequirements",
    "ToolRuntimeFact",
    "missing_tool_requirements",
]
