"""Turning an agent's grants into what a query may actually search.

This is the security boundary of the knowledgebase, and it is small on purpose.
Everything an agent can reach passes through `readable_scopes`; everything it
can change passes through `assert_writable`.

The rule both enforce: **a missing filter must never widen access.** An agent
with no grants gets an empty mapping, and every vendor treats an empty mapping
as "search nothing" rather than "search everything". That inversion is the
difference between scoping and decoration.
"""

from __future__ import annotations

from eylo.common.contracts.knowledgebase import KnowledgeAccess, KnowledgeScope


class KnowledgeAccessError(Exception):
    """An agent asked for something its grants do not permit."""


def readable_scopes(
    grant,
    *,
    requested: list[KnowledgeScope] | None = None,
    conversation_id=None,
) -> dict[KnowledgeScope, str]:
    """The one granted KB scope that is active in the current context.

    Taking one grant makes it impossible for same-scope KBs to overwrite each
    other in an intermediate dict. Conversation-scoped knowledge is available
    only while that exact conversation is active; a grant alone does not turn
    it into agent-wide knowledge.
    """
    knowledgebase = grant.knowledgebase
    scope = knowledgebase.scope
    if requested is not None and scope not in requested:
        return {}
    if scope is KnowledgeScope.CONVERSATION and (
        conversation_id is None
        or str(knowledgebase.scope_id) != str(conversation_id)
    ):
        return {}
    return {scope: knowledgebase.scope_id}


def assert_writable(
    grants: list,
    knowledgebase_id,
    *,
    conversation_id=None,
) -> None:
    """Raise unless this agent may write to this knowledgebase.

    Two conditions, and both must hold: the KB itself accepts writes, and the
    grant carries READ_WRITE. A grant cannot exceed its knowledgebase, so an
    append-only source stays read-only however generously it is granted.

    Raises rather than returning False. A silently ignored write is the failure
    mode where an agent believes it recorded something and did not — worse than
    an error the model can relay.
    """
    # Compared as strings, and not out of laziness. This codebase produces
    # UUIDs from three sources — `uuid_utils.UUID` from a Python-side default,
    # `asyncpg.pgproto.UUID` from a loaded row, and stdlib `uuid.UUID` from a
    # parsed path parameter — and they do not compare equal to each other even
    # when they hold the same value. Here that would silently deny a write the
    # operator did grant, and the message would say "no grant" while the grant
    # sits in the table.
    target = str(knowledgebase_id)
    grant = next(
        (g for g in grants if str(g.knowledgebase_id) == target), None
    )
    if grant is None:
        raise KnowledgeAccessError(
            f"This agent has no grant for knowledgebase {knowledgebase_id}."
        )

    # By name, falling back to the id. These messages reach a model, which
    # relays them to a person; "the Product Docs knowledgebase is read-only" is
    # something an operator can act on and a UUID is not.
    named = getattr(grant.knowledgebase, "name", None) or knowledgebase_id

    if not grant.knowledgebase.writable:
        raise KnowledgeAccessError(
            f"Knowledgebase '{named}' does not accept writes."
        )
    if grant.access is not KnowledgeAccess.READ_WRITE:
        raise KnowledgeAccessError(
            f"This agent has read-only access to knowledgebase '{named}'. "
            "Grant READ_WRITE to allow writing."
        )
    if grant.knowledgebase.scope is KnowledgeScope.CONVERSATION and (
        conversation_id is None
        or str(grant.knowledgebase.scope_id) != str(conversation_id)
    ):
        raise KnowledgeAccessError(
            f"Knowledgebase '{named}' is not available in this conversation."
        )
