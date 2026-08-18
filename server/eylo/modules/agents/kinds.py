"""Enforce Agent kind, swarm, implementation, and attachment invariants."""

from __future__ import annotations

from eylo.modules.agents.exceptions import AgentError
from eylo.modules.agents.implementations import is_registered, known_slugs
from eylo.modules.agents.models import AgentKind


class InvalidAgentKindError(AgentError):
    """An operation is not valid for this agent's kind."""


class UnknownImplementationError(AgentError):
    """An `implementation` slug that no first-party code answers to."""


def assert_can_join_swarm(kind: AgentKind, agent_id) -> None:
    """Swarms are how handoffs are configured, so this closes both directions."""
    if kind is AgentKind.BACKGROUND:
        raise InvalidAgentKindError(
            f"Agent {agent_id} is a BACKGROUND agent and cannot join a swarm. "
            "Swarm membership is how handoffs are configured, and a background "
            "run has nobody supervising it, so it must be unreachable by "
            "handoff in either direction."
        )


def assert_implementation_is_valid(
    kind: AgentKind, implementation: str | None
) -> None:
    """Reject an implementation slug at write time rather than at dispatch.

    A typo that survives to dispatch becomes a background agent that silently
    does nothing, which is the failure mode this codebase keeps removing.
    """
    if implementation is None:
        return

    if kind is not AgentKind.BACKGROUND:
        raise InvalidAgentKindError(
            "Only a BACKGROUND agent may set `implementation`; it names "
            "first-party code that runs on dispatch, and a conversational "
            "agent has no dispatch path that would ever call it."
        )

    if not is_registered(implementation):
        known = known_slugs()
        raise UnknownImplementationError(
            f"Unknown background agent implementation {implementation!r}. "
            + (
                f"Known implementations: {', '.join(known)}."
                if known
                else "No first-party implementations are registered, so a "
                "background agent must be prompt-only (implementation = null)."
            )
        )


def assert_can_have_background_agents(kind: AgentKind, agent_id) -> None:
    """No chaining: a background agent may not own attachments of its own."""
    if kind is AgentKind.BACKGROUND:
        raise InvalidAgentKindError(
            f"Agent {agent_id} is a BACKGROUND agent and cannot have "
            "background agents attached to it. Chaining would let one "
            "unsupervised run spawn another without bound."
        )


def assert_is_background(kind: AgentKind, agent_id) -> None:
    """The attachment target must actually be a background agent."""
    if kind is not AgentKind.BACKGROUND:
        raise InvalidAgentKindError(
            f"Agent {agent_id} is {kind.value} and cannot be attached as a "
            "background agent. Only a BACKGROUND agent has a dispatch path."
        )


def assert_is_conversational(kind: AgentKind, agent_id) -> None:
    """The attachment owner must be the side that actually completes runs."""
    if kind is not AgentKind.CONVERSATIONAL:
        raise InvalidAgentKindError(
            f"Agent {agent_id} is {kind.value} and cannot own background agent "
            "attachments. Dispatch is triggered by a conversational run "
            "completing, which is the only thing a background agent does not do."
        )


def assert_attachment_is_valid(
    *,
    owner_kind: AgentKind,
    owner_id,
    owner_organization_id,
    target_kind: AgentKind,
    target_id,
    target_organization_id,
) -> None:
    """All four attachment invariants, checked together.

    Kept as one call so a caller cannot satisfy three of them and forget the
    fourth. Ordered so the most specific complaint wins: telling an operator
    "that is a conversational agent" is more use than "those are in different
    organizations" when both are true.
    """
    if owner_id == target_id:
        raise InvalidAgentKindError(
            f"Agent {owner_id} cannot be attached to itself. Dispatch happens "
            "when its run completes, so this would re-enter on every turn."
        )

    assert_is_conversational(owner_kind, owner_id)
    assert_can_have_background_agents(owner_kind, owner_id)
    assert_is_background(target_kind, target_id)

    if owner_organization_id != target_organization_id:
        raise InvalidAgentKindError(
            f"Agents {owner_id} and {target_id} belong to different "
            "organizations and cannot be attached."
        )
