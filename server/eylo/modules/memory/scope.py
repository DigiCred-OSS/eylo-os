"""One executable derivation of Agent, User, and Conversation memory authority."""

from __future__ import annotations

from uuid import UUID

from eylo.common.contracts.memory import MemoryError, MemoryLevel, MemoryScope


def scope_from_context(conversation_context, agent=None) -> MemoryScope | None:
    """Resolve the Conversation scope used by automatic formation."""
    return scope_for_level(conversation_context, MemoryLevel.CONVERSATION, agent=agent)


def scope_for_level(
    conversation_context,
    level: MemoryLevel,
    *,
    agent=None,
) -> MemoryScope | None:
    """Derive one exact owner from trusted runtime context, never model input."""
    if conversation_context is None:
        return None

    conversation = getattr(conversation_context, "conversation", None)
    selected_agent = agent or getattr(conversation_context, "primary_agent", None)
    if conversation is None or selected_agent is None:
        return None

    conversation_id = _uuid(getattr(conversation, "id", None))
    conversation_organization_id = getattr(conversation, "organization_id", None)
    agent_organization_id = getattr(selected_agent, "organization_id", None)
    if conversation_id is None or conversation_organization_id is None:
        return None
    if agent_organization_id != conversation_organization_id:
        raise MemoryError("Memory conversation authority is inconsistent.")

    if level is MemoryLevel.CONVERSATION:
        owner_id = conversation_id
    elif level is MemoryLevel.AGENT:
        owner_id = _agent_owner(conversation_context, selected_agent, conversation_id)
    else:
        owner_id = _user_owner(
            conversation_context,
            conversation_organization_id,
            conversation_id,
        )

    return MemoryScope(
        organization_id=conversation_organization_id,
        level=level,
        owner_id=owner_id,
    )


def authorized_scopes_from_context(conversation_context, agent=None) -> tuple[MemoryScope, ...]:
    """Return every exact scope the active Agent may recall, widest last."""
    scopes = []
    for level in (
        MemoryLevel.CONVERSATION,
        MemoryLevel.USER,
        MemoryLevel.AGENT,
    ):
        scope = scope_for_level(conversation_context, level, agent=agent)
        if scope is None:
            return ()
        scopes.append(scope)
    return tuple(scopes)


def _agent_owner(conversation_context, selected_agent, conversation_id: UUID) -> UUID:
    participant = conversation_context.get_primary_agent()
    selected_agent_id = _uuid(getattr(selected_agent, "id", None))
    if (
        participant is None
        or selected_agent_id is None
        or _uuid(getattr(participant, "conversation_id", None)) != conversation_id
        or _uuid(getattr(participant, "agent_id", None)) != selected_agent_id
        or getattr(participant, "agent_revision", None) is None
    ):
        raise MemoryError("Memory Agent authority is inconsistent.")
    return selected_agent_id


def _user_owner(
    conversation_context,
    organization_id: UUID,
    conversation_id: UUID,
) -> UUID:
    contact = getattr(conversation_context, "primary_contact", None)
    participant = conversation_context.get_primary_contact()
    contact_id = _uuid(getattr(contact, "id", None))
    participant_entity_id = _uuid(getattr(participant, "entity_id", None))
    if (
        contact is None
        or participant is None
        or contact_id is None
        or _uuid(getattr(contact, "organization_id", None)) != organization_id
        or _uuid(getattr(participant, "conversation_id", None)) != conversation_id
        or participant_entity_id != contact_id
    ):
        raise MemoryError("Memory User authority is inconsistent.")
    return contact_id


def _uuid(value) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


__all__ = [
    "authorized_scopes_from_context",
    "scope_for_level",
    "scope_from_context",
]
