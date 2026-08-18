"""Registered Agent-reminder system tool."""

from typing import Any, Dict
from uuid import UUID, uuid4

import arrow

from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.tools.services.executors.system_tools import logger


async def set_agent_reminder(
    datetime_str: str, message: str, ctx: ConversationContext
) -> Dict[str, Any]:
    """Schedule one user-requested conversation re-engagement.

    Use only when the user explicitly asks to be reminded or contacted later.
    After success, acknowledge the schedule, end naturally, and call no more
    tools. The durable scheduler will restart the conversation at the requested
    instant.

    Args:
        datetime_str: Future ISO 8601 UTC timestamp.
        message: Brief context for the later conversation.

    Returns:
        Scheduling result. A successful result sets ``action_required`` to
        ``end_scheduling_task`` and includes the exact UTC instant.

    """
    try:
        dt = arrow.get(datetime_str)
        now = arrow.utcnow()

        if dt <= now:
            return {
                "success": False,
                "message": f"Time must be in the future. Current UTC: {now.isoformat()}",
                "action_required": "ask_user_for_new_time",
            }

        agent_indb: AgentInDb = ctx.primary_agent
        conversation_id: UUID = ctx.conversation.id
        sender_participant_id: UUID = ctx.get_primary_contact().id

        if not all([agent_indb, conversation_id, sender_participant_id]):
            return {
                "success": False,
                "message": "System error: Missing conversation context",
                "action_required": "apologize_and_ask_to_retry",
            }

        # Through the scheduler, as a one-shot schedule. This used to write to
        # `tool_agent_schedules` and be picked up by a cron that only looked
        # four hours back — so a reminder due during a longer outage was
        # silently never delivered. The occurrence now survives the outage and
        # fires late, recording that it was late.
        #
        # UTC, not the caller's timezone: the tool takes an absolute instant,
        # so there is no wall-clock intent to preserve. A recurring reminder
        # would need the user's timezone, which is why this stays one-shot.
        from eylo.common.contracts.scheduler import Recurrence
        from eylo.modules.scheduler.service import create_schedule

        await create_schedule(
            organization_id=agent_indb.organization_id,
            # Unique per reminder. Reminders accumulate rather than replace —
            # two reminders for the same conversation are two reminders, so a
            # stable key would have the second silently overwrite the first.
            key=f"reminder:{conversation_id}:{uuid4()}",
            name=f"Reminder for conversation {conversation_id}",
            action="conversation.reengage",
            payload={
                "conversation_id": str(conversation_id),
                "message": message,
            },
            recurrence=Recurrence(rule=None, timezone="UTC", starts_at=dt.datetime),
            agent_id=agent_indb.id,
            agent_revision=agent_indb.published_revision,
        )

        friendly_time = dt.to("UTC").format("YYYY-MM-DD at HH:mm") + " UTC"

        return {
            "success": True,
            "scheduled_time_utc": dt.to("UTC").isoformat(),
            "message": f"Reminder successfully scheduled for {friendly_time}. The system will automatically re-engage the conversation at that time.",
            "action_required": "end_scheduling_task",
            "reminder_context": message,
            # Add this critical flag:
            "_meta": {"conversation_complete": True, "no_further_actions_needed": True},
        }

    except arrow.parser.ParserError:
        return {
            "success": False,
            "message": f"Invalid datetime format. Use ISO 8601 UTC (e.g., '2025-10-11T14:30:00Z'). Current time: {arrow.utcnow().isoformat()}",
            "action_required": "ask_user_for_correct_format",
        }
    except Exception as error:
        logger.error(
            "set_agent_reminder failed error_type=%s",
            type(error).__name__,
        )
        return {
            "success": False,
            "message": "System error setting reminder. Please try again.",
            "action_required": "apologize_and_offer_retry",
        }
