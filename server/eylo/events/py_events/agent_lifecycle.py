"""Bounded agent lifecycle event production.

Lifecycle events are lossy UI deltas. This adapter projects only stable IDs and
correlation metadata so a large conversation context can never make the event
silently exceed the ephemeral event limit.
"""

from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID, uuid4

from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.base import (
    AgentLifecycleEvent,
    AgentLifecycleOutcome,
    AgentResponseCompleteEvent,
)
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.participants import ParticipantKind


class AgentLifecycleEmitter:
    """Emit one monotonic, request-scoped lifecycle stream at a time."""

    def __init__(self) -> None:
        self._request_id: UUID | None = None
        self._run_id: UUID | None = None
        self._run_started_at: datetime.datetime | None = None
        self._sequence = 0

    def emit(
        self,
        event_type: type[AgentLifecycleEvent],
        *,
        context: ConversationContext,
        request_id: UUID,
        message_id: UUID | None = None,
        outcome: AgentLifecycleOutcome | None = None,
    ) -> None:
        self._start_request_if_needed(request_id)
        self._sequence += 1

        payload: dict[str, Any] = {
            "organization_id": context.conversation.organization_id,
            "conversation_id": context.conversation.id,
            "contact_ids": tuple(
                participant.entity_id
                for participant in context.participants
                if participant.entity_kind == ParticipantKind.CONTACT
            ),
            "request_id": request_id,
            "message_id": message_id,
            "run_id": self._run_id,
            "run_started_at": self._run_started_at,
            "sequence": self._sequence,
        }
        if event_type is AgentResponseCompleteEvent:
            if outcome is None:
                raise ValueError("Terminal agent lifecycle event requires an outcome.")
            payload["outcome"] = outcome
        elif outcome is not None:
            raise ValueError("Only terminal agent lifecycle events accept an outcome.")

        emit_ephemeral(event_type(**payload))

    def _start_request_if_needed(self, request_id: UUID) -> None:
        if self._request_id == request_id:
            return
        self._request_id = request_id
        self._run_id = uuid4()
        self._run_started_at = datetime.datetime.now(datetime.UTC)
        self._sequence = 0
