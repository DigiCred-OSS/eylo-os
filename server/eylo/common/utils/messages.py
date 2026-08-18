"""Message grouping utilities.

Pure functions for grouping and sorting platform messages by request_id.
These are used by the LLM adapter layer but live here as common utilities
so other parts of the platform can reuse them without importing from sockets/.
"""

from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from eylo.modules.conversations.schemas.messages import MessageInDb


def group_messages_by_request_id(
    messages: List[MessageInDb],
) -> Dict[UUID, List[MessageInDb]]:
    """Group messages by request_id in chronological order.

    Args:
        messages: Messages to group. Must all have a non-null request_id.

    Returns:
        Dict mapping each request_id to its ordered list of messages.

    Raises:
        ValueError: If any message is missing a request_id.

    """
    grouped: Dict[UUID, List[MessageInDb]] = {}
    for msg in sorted(messages, key=lambda m: m.created_at):
        if not msg.request_id:
            raise ValueError(f"Message {msg.id} missing request_id")
        grouped.setdefault(msg.request_id, []).append(msg)
    return grouped


def sort_request_groups_by_user_message(
    messages: List[MessageInDb],
) -> List[UUID]:
    """Return request IDs sorted by the chronological order of their USER messages.

    Args:
        messages: All messages across all request groups.

    Returns:
        Deduplicated list of request_ids ordered by their earliest USER message.

    """
    from eylo.modules.conversations.schemas.messages import MessageKind

    user_messages = sorted(
        (m for m in messages if m.kind == MessageKind.USER),
        key=lambda m: m.created_at,
    )
    seen: list[UUID] = []
    for m in user_messages:
        if m.request_id and m.request_id not in seen:
            seen.append(m.request_id)
    return seen
