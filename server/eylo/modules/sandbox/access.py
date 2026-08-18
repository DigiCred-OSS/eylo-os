"""Explicit no-egress permission to run code."""

from __future__ import annotations

from eylo.common.contracts.sandbox import SandboxError


class SandboxAccessError(SandboxError):
    """An agent asked to do something its grant does not permit."""


def find_grant(grants: list, agent_id):
    """This agent's grant, or None.

    Compared as strings. This codebase produces `uuid_utils.UUID` from
    Python-side defaults, `asyncpg.pgproto.UUID` from loaded rows and stdlib
    `uuid.UUID` from parsed path parameters, and none compare equal to each
    other holding the same value — a mismatch here would silently deny an agent
    the operator did grant, which is the failure the knowledgebase found.
    """
    target = str(agent_id)
    return next((g for g in grants if str(g.agent_id) == target), None)


def assert_can_run(grants: list, agent_id) -> None:
    """Raise unless this agent may execute code at all.

    Raises rather than returning False. A silently skipped execution is the
    failure mode where an agent believes it ran something and did not — worse
    than an error the model can relay, because the agent will go on to report
    results it never obtained.
    """
    if find_grant(grants, agent_id) is None:
        raise SandboxAccessError(
            "This agent has no sandbox grant, so it cannot run code. "
            "Configuring a sandbox for an organization does not grant it to "
            "every agent — grant it to this one explicitly."
        )


def session_limit(grants: list, agent_id, *, organization_limit: int) -> int:
    """How many workspaces this agent may hold.

    Narrowed by the grant, never widened. An agent granted more than its
    organization allows gets its organization's number — the config is the
    ceiling and the grant is a further restriction within it.
    """
    grant = find_grant(grants, agent_id)
    if grant is None or grant.max_sessions is None:
        return organization_limit
    return min(grant.max_sessions, organization_limit)
