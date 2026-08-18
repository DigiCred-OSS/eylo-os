"""Registered scheduling system tools."""

from typing import Any
from uuid import uuid4

import arrow

from eylo.common.contracts.scheduler import InvalidRecurrence, Recurrence
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.scheduler.actions import action_spec, agent_actions
from eylo.modules.scheduler.discovery import register_scheduled_actions
from eylo.modules.scheduler.service import (
    ScheduleNotFound,
    cancel_schedule,
    create_schedule,
    list_schedules,
)
from eylo.modules.tools.services.executors.system_tools import logger

MAX_LISTED = 20


async def schedule_create(
    action: str,
    starts_at: str,
    rule: str | None = None,
    timezone: str | None = None,
    payload: dict | None = None,
    name: str | None = None,
    ctx: ConversationContext = None,
) -> dict[str, Any]:
    """Schedule something to happen later, once or on a repeating rule.

    Use this for anything the user wants at a future time — a reminder, a
    recurring check-in, a report every morning, or picking a task back up after
    a delay.

    Args:
        action (str): What to do. Call this tool with action='list' to see
            what is available.
        starts_at (str): ISO 8601 timestamp for the first occurrence, e.g.
            '2026-08-01T09:00:00Z'. Must be in the future.
        rule (str | None): For repeats, an RFC 5545 rule such as
            'FREQ=DAILY', 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR', or
            'FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1' for the last
            weekday of the month. Omit for a one-off.
        timezone (str | None): IANA name such as 'Europe/Berlin'. **Required
            for repeating schedules** — "every morning at 9" means 9am where
            the user is, and it must survive daylight saving. Ask the user if
            you do not know it.
        payload (dict | None): Extra data for the action. Anything the
            platform owns — such as which conversation this is — is filled in
            for you and cannot be set here.
        name (str | None): A short human-readable label.

    Returns:
        Dict with keys:
        - success (bool)
        - schedule_id (str): Present on success; needed to cancel it.
        - next_at (str): When it will first run.
        - message (str): On failure, what to fix.

    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {"success": False, "message": "No agent in context."}
    if agent.published_revision is None:
        return {
            "success": False,
            "message": "The active agent context has no exact published revision.",
        }

    register_scheduled_actions()
    available = agent_actions()

    if action == "list" or action not in available:
        return {
            "success": False,
            "available_actions": list(available),
            "message": f"Choose one of: {', '.join(available) or 'none available'}.",
        }

    # A repeating schedule without a timezone is one that fires at the wrong
    # hour for most of the world, twice a year. Refusing beats guessing UTC.
    if rule and not timezone:
        return {
            "success": False,
            "message": (
                "A repeating schedule needs a timezone, e.g. 'Europe/Berlin'. "
                "Ask the user which timezone they are in."
            ),
        }

    try:
        when = arrow.get(starts_at)
    except Exception:  # noqa: BLE001 - arrow raises several parse errors
        return {
            "success": False,
            "message": (
                f"'{starts_at}' is not an ISO 8601 timestamp. Use a form like "
                f"'2026-08-01T09:00:00Z'. Current UTC: {arrow.utcnow().isoformat()}"
            ),
        }
    if when <= arrow.utcnow():
        return {
            "success": False,
            "message": f"That time has passed. Current UTC: {arrow.utcnow().isoformat()}",
        }

    # Context-owned keys overwrite model input so tenant and conversation
    # identity never become model-supplied authority.
    spec = action_spec(action)
    resolved = dict(payload or {})
    supplied = [key for key in spec.context_keys if key in resolved]
    if supplied:
        logger.warning(
            "Agent supplied platform-owned schedule keys agent=%s count=%d; ignored",
            agent.id,
            len(supplied),
        )
    for key in spec.context_keys:
        resolved[key] = _from_context(key, ctx)
        if resolved[key] is None:
            return {
                "success": False,
                "message": (
                    f"This action needs a {key.replace('_', ' ')}, and there is "
                    "none in this conversation."
                ),
            }

    try:
        schedule_id, first = await create_schedule(
            organization_id=agent.organization_id,
            key=f"agent:{agent.id}:{uuid4()}",
            name=name or f"{action} scheduled by agent",
            action=action,
            payload=resolved,
            recurrence=Recurrence(
                rule=rule,
                timezone=timezone or "UTC",
                starts_at=when.datetime,
            ),
            agent_id=agent.id,
            agent_revision=agent.published_revision,
        )
    except InvalidRecurrence:
        return {"success": False, "message": "Schedule recurrence is invalid."}

    return {
        "success": True,
        "schedule_id": str(schedule_id),
        "next_at": first.isoformat() if first else None,
        "message": f"Scheduled. First run {first.isoformat() if first else 'unknown'}.",
    }


async def schedule_list(ctx: ConversationContext = None) -> dict[str, Any]:
    """List the schedules you have created, and when each next runs.

    Only your own. Schedules an operator set up are not yours to see or change.

    Returns:
        Dict with keys:
        - success (bool)
        - schedules (list): Each with schedule_id, name, action, next_at and
          whether it is still active.

    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {"success": False, "schedules": [], "message": "No agent in context."}

    rows = await list_schedules(
        organization_id=agent.organization_id, agent_id=agent.id, limit=MAX_LISTED
    )
    return {
        "success": True,
        "schedules": [
            {
                "schedule_id": str(row.id),
                "name": row.name,
                "action": row.action,
                "next_at": row.next_at.isoformat() if row.next_at else None,
                "repeating": row.rule is not None,
                "active": row.enabled and row.retired_at is None,
            }
            for row in rows
        ],
        "message": "" if rows else "You have no schedules.",
    }


async def schedule_cancel(
    schedule_id: str, ctx: ConversationContext = None
) -> dict[str, Any]:
    """Cancel a schedule you created, so it stops running.

    Args:
        schedule_id (str): From `schedule_list`.

    Returns:
        Dict with success and a message. Cancelling something that is not
        yours fails — it does not silently do nothing.

    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {"success": False, "message": "No agent in context."}

    from uuid import UUID

    try:
        target = UUID(schedule_id)
    except ValueError:
        return {"success": False, "message": f"'{schedule_id}' is not a schedule id."}

    try:
        await cancel_schedule(
            target, organization_id=agent.organization_id, agent_id=agent.id
        )
    except ScheduleNotFound:
        # Same answer whether it never existed or belongs to someone else.
        # Distinguishing them would let an agent probe for other schedules.
        return {
            "success": False,
            "message": "No schedule of yours with that id.",
        }
    return {"success": True, "message": "Cancelled."}


def _from_context(key: str, ctx: ConversationContext):
    """Resolve a platform-owned payload key from the conversation.

    Only keys named here can ever be filled, so an action declaring a key this
    does not know fails loudly rather than scheduling with it missing.
    """
    if key == "conversation_id":
        conversation = getattr(ctx, "conversation", None)
        return str(conversation.id) if conversation else None
    return None


_from_context.__eylo_hidden__ = True  # type: ignore[attr-defined]
