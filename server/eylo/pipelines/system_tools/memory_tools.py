"""Agent Memory tools backed by exact runtime-derived ownership.

The model chooses only `agent`, `user`, or `conversation`. Organization and
subject IDs always come from the validated ConversationContext. Mutations name
the level again so a recalled ID cannot widen its own authority.
"""

from typing import Any
from uuid import UUID

from eylo.common.contracts.memory import MemoryError, MemoryLevel
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.tools.services.executors.system_tools import logger
from eylo.pipelines.memory.application import (
    forget_context_fact,
    recall_context_memory,
    refresh_context_fact,
    remember_context_fact,
)

MAX_RESULTS = 5

_NOT_CONFIGURED = (
    "Memory is not configured for this organization, so there is nothing to "
    "remember with. This is not the same as finding no matching fact."
)
_NO_CONTEXT = {"success": False, "message": "No conversation in context."}


async def memory_recall(
    query: str,
    ctx: ConversationContext | None = None,
) -> dict[str, Any]:
    """Recall relevant Agent, User, and Conversation memories.

    Use this when prior learned facts could help answer or act now. Results are
    globally ranked across all three levels. Keep each returned `id` and
    `level` together if you later need to refresh or forget that exact fact.

    Args:
        query (str): What to recall, written as a natural-language question.

    Returns:
        `success`, ordered `memories` (`id`, `level`, `content`, `score`), and
        a `message` when nothing matched or Memory is unavailable.

    """
    if ctx is None:
        return {**_NO_CONTEXT, "memories": [], "conflicts": []}

    try:
        recall = await recall_context_memory(ctx, query, limit=MAX_RESULTS)
    except NotConfiguredError:
        return {
            "success": False,
            "memories": [],
            "conflicts": [],
            "message": _NOT_CONFIGURED,
        }
    except MemoryError as error:
        logger.warning("Memory recall failed: %s", type(error).__name__)
        return {
            "success": False,
            "memories": [],
            "conflicts": [],
            "message": "Memory is unavailable right now.",
        }

    found = recall.memories
    return {
        "success": True,
        "memories": [
            {
                "id": str(memory.id),
                "level": memory.scope.level.value,
                "content": memory.content,
                "score": memory.score,
            }
            for memory in found
        ],
        "conflicts": [
            {
                "relationship_id": str(conflict.relationship_id),
                "level": conflict.facts[0].scope.level.value,
                "facts": [
                    {"id": str(fact.id), "content": fact.content}
                    for fact in conflict.facts
                ],
            }
            for conflict in recall.conflicts
        ],
        "message": (
            "Unresolved memory conflicts require user clarification."
            if recall.conflicts
            else "" if found else "Nothing remembered that matches."
        ),
        "ranking": recall.ranking.model_dump(mode="json"),
    }


async def memory_remember(
    fact: str,
    level: MemoryLevel,
    ctx: ConversationContext | None = None,
) -> dict[str, Any]:
    """Remember a fact at the Agent, User, or Conversation level.

    Choose `agent` for reusable knowledge learned by this Agent, `user` for a
    preference or detail about the current User, and `conversation` for working
    context that matters only inside this extended conversation. The fact is
    reconciled with existing memories, so it may add, update, or do nothing.

    Args:
        fact (str): A standalone fact without turn-dependent pronouns.
        level (MemoryLevel): `agent`, `user`, or `conversation`.

    Returns:
        `success`, the exact inferred `changes`, and a status `message`.

    """
    if ctx is None:
        return {**_NO_CONTEXT, "changes": []}
    if not fact.strip():
        return {"success": False, "changes": [], "message": "Nothing to remember."}

    try:
        operations = await remember_context_fact(ctx, fact, level=level)
    except NotConfiguredError:
        return {"success": False, "changes": [], "message": _NOT_CONFIGURED}
    except MemoryError as error:
        logger.warning("Memory remember failed: %s", type(error).__name__)
        return {
            "success": False,
            "changes": [],
            "message": "Memory is unavailable right now.",
        }

    changes = [
        {
            "event": operation.event.value,
            "content": operation.content,
            "memory_id": str(operation.target_id) if operation.target_id else None,
        }
        for operation in operations
    ]
    return {
        "success": True,
        "changes": changes,
        "message": "" if changes else "No memory change was needed.",
    }


async def memory_refresh(
    memory_id: UUID,
    level: MemoryLevel,
    fact: str,
    ctx: ConversationContext | None = None,
) -> dict[str, Any]:
    """Refresh one active memory while preserving its identity and history.

    Use the `id` and `level` returned by `memory_recall`. This is an exact
    correction, not another extraction pass. Expired or foreign facts are not
    revealed and cannot be refreshed.

    Args:
        memory_id (UUID): Exact ID returned by `memory_recall`.
        level (MemoryLevel): The level returned with that ID.
        fact (str): The complete corrected standalone fact.

    Returns:
        `success`, refreshed `memory`, and a status `message`.

    """
    if ctx is None:
        return {**_NO_CONTEXT, "memory": None}
    try:
        memory = await refresh_context_fact(
            ctx,
            memory_id,
            fact,
            level=level,
        )
    except NotConfiguredError:
        return {"success": False, "memory": None, "message": _NOT_CONFIGURED}
    except MemoryError as error:
        logger.warning("Memory refresh failed: %s", type(error).__name__)
        return {
            "success": False,
            "memory": None,
            "message": "No active memory was found at that level.",
        }
    return {
        "success": True,
        "memory": {
            "id": str(memory.id),
            "level": memory.scope.level.value,
            "content": memory.content,
        },
        "message": "Memory refreshed.",
    }


async def memory_forget(
    memory_id: UUID,
    level: MemoryLevel,
    ctx: ConversationContext | None = None,
) -> dict[str, Any]:
    """Expire one active memory so Agents no longer recall it.

    Use the `id` and `level` returned by `memory_recall`. Forgetting is not hard
    deletion: operators can still inspect the expired fact and its history.

    Args:
        memory_id (UUID): Exact ID returned by `memory_recall`.
        level (MemoryLevel): The level returned with that ID.

    Returns:
        `success`, `expired`, and a status `message`.

    """
    if ctx is None:
        return {**_NO_CONTEXT, "expired": False}
    try:
        expired = await forget_context_fact(ctx, memory_id, level=level)
    except NotConfiguredError:
        return {"success": False, "expired": False, "message": _NOT_CONFIGURED}
    except MemoryError as error:
        logger.warning("Memory forget failed: %s", type(error).__name__)
        return {
            "success": False,
            "expired": False,
            "message": "Memory is unavailable right now.",
        }
    return {
        "success": expired,
        "expired": expired,
        "message": "Memory expired." if expired else "No active memory was found at that level.",
    }


__all__ = [
    "memory_forget",
    "memory_recall",
    "memory_refresh",
    "memory_remember",
]
