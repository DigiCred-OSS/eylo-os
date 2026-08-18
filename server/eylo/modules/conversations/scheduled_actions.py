"""Conversation capabilities a schedule can invoke.

Registered with the scheduler's action registry, which is what lets this live
here — in the module that owns the behaviour — rather than inside the
scheduler. The scheduler never learns what a conversation is.
"""

from __future__ import annotations

import logging

import arrow

from eylo.common.database import get_transaction, start_transaction
from eylo.modules.conversations.schemas.message_content import UserMessageContent
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageKind,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.scheduler.actions import ActionContext, schedulable

logger = logging.getLogger(__name__)


@schedulable(
    "conversation.reengage",
    # The platform fills this from the conversation the agent is in. An agent
    # that could name a conversation could name someone else's.
    context_keys=("conversation_id",),
    agent_schedulable=True,
)
async def reengage(payload: dict, *, context: ActionContext) -> dict:
    """Restart a conversation by posting a message as if the contact sent it."""
    conversation_id = payload.get("conversation_id")
    message = (payload.get("message") or "").strip()

    if not conversation_id:
        # Terminal by nature: a payload missing this will miss it on every
        # retry. Raising is right; the run records why and stops.
        raise ValueError("conversation.reengage requires a conversation_id.")
    if not message:
        raise ValueError("conversation.reengage requires a message.")

    async with start_transaction():
        session = get_transaction()
        participants = await ConversationParticipantService(
            session
        ).get_contact_participant_from_conversation(conversation_id)
        if not participants:
            raise ValueError(
                f"Conversation {conversation_id} has no contact participant to "
                "attribute the message to."
            )

        created = await MessageService(session).create_(
            MessageCreate(
                conversation_id=conversation_id,
                sender_participant_id=participants[0].id,
                kind=MessageKind.USER,
                content_kind=MessageContentKind.TEXT,
                # `UserMessageContent`, not a bare `{"text": ...}` dict. The
                # old executor passed the latter, which does not satisfy the
                # schema — `role` and `content` are both required — so every
                # reminder it ever processed raised a ValidationError, was
                # swallowed by its blanket except, and was marked FAILED. The
                # user was simply never re-engaged. Porting is what surfaced
                # it: the same call, made somewhere the error was not
                # swallowed, failed immediately and visibly.
                content=UserMessageContent(content=message),
                created_at=arrow.utcnow().datetime,
            )
        )

    if context.misfired_count:
        # The agent is about to speak later than intended. Recorded here rather
        # than only on the run, so it appears beside the message it explains.
        logger.info(
            "Re-engaged conversation %s late; %d earlier occurrence(s) were "
            "coalesced into this one.",
            conversation_id, context.misfired_count,
        )

    return {
        "conversation_id": str(conversation_id),
        "message_id": str(getattr(created, "id", "")) or None,
        "late_by_occurrences": context.misfired_count,
    }
