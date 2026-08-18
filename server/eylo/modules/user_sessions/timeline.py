"""Closed, privacy-safe projection of durable facts onto a session timeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eylo.events.durable.models import EventOutboxModel
from eylo.modules.user_sessions.schemas import (
    TimelineCategory,
    TimelineSeverity,
    UserSessionTimelineEventRead,
)


@dataclass(frozen=True, slots=True)
class TimelineEventDefinition:
    category: TimelineCategory
    label: str
    detail_keys: frozenset[str]
    technical: bool = False
    severity: TimelineSeverity = TimelineSeverity.DEFAULT


_IDS = frozenset(
    {
        "agent_id",
        "agent_run_id",
        "conversation_id",
        "document_id",
        "from_agent_id",
        "input_request_id",
        "knowledgebase_id",
        "origin_message_id",
        "request_id",
        "run_id",
        "to_agent_id",
        "tool_call_id",
        "voice_session_id",
    }
)
_STATE = frozenset(
    {
        "channel",
        "connection_sequence",
        "content_kind",
        "current_status",
        "direction",
        "entry_channel",
        "failure_code",
        "kind",
        "outcome",
        "previous_status",
        "provider",
        "provider_kind",
        "reason",
        "request_kind",
        "request_status",
        "runtime_mode",
        "status",
        "tool_name",
        "transport",
        "vendor",
    }
)
_COUNTS = frozenset(
    {
        "agent_revision",
        "byte_size",
        "connection_sequence",
        "duration_ms",
        "duration_seconds",
    }
)


def _definition(
    category: TimelineCategory,
    label: str,
    *,
    details: frozenset[str] = frozenset(),
    technical: bool = False,
    danger: bool = False,
) -> TimelineEventDefinition:
    return TimelineEventDefinition(
        category=category,
        label=label,
        detail_keys=details,
        technical=technical,
        severity=TimelineSeverity.DANGER if danger else TimelineSeverity.DEFAULT,
    )


TIMELINE_EVENT_CATALOG: dict[str, TimelineEventDefinition] = {
    "user.session.started": _definition(
        TimelineCategory.SESSION,
        "Session started",
        details=frozenset({"entry_channel", "connection_sequence"}),
    ),
    "user.session.reconnected": _definition(
        TimelineCategory.SESSION,
        "Session reconnected",
        details=frozenset({"connection_sequence"}),
    ),
    "user.session.disconnected": _definition(
        TimelineCategory.SESSION,
        "Session disconnected",
        details=frozenset({"reason", "connection_sequence"}),
    ),
    "user.session.ended": _definition(
        TimelineCategory.SESSION,
        "Session ended",
        details=frozenset({"reason", "connection_sequence"}),
    ),
    "user.session.failed": _definition(
        TimelineCategory.SESSION,
        "Session failed",
        details=frozenset({"reason", "connection_sequence"}),
        danger=True,
    ),
    "conversation.started": _definition(
        TimelineCategory.CONVERSATION,
        "Conversation started",
        details=_IDS | frozenset({"channel"}),
    ),
    "conversation.continued": _definition(
        TimelineCategory.CONVERSATION,
        "Conversation continued",
        details=_IDS | frozenset({"channel"}),
    ),
    "message.created": _definition(
        TimelineCategory.MESSAGE,
        "Message created",
        details=_IDS | _STATE,
    ),
    **{
        f"message.request.{state}": _definition(
            TimelineCategory.MESSAGE,
            f"Message request {state.replace('_', ' ')}",
            details=_IDS | _STATE,
            danger=state == "failed",
        )
        for state in (
            "processing",
            "awaiting_tool_results",
            "completed",
            "failed",
            "interrupted",
            "skipped",
        )
    },
    **{
        f"agent.run.{state}": _definition(
            TimelineCategory.AGENT,
            f"Agent run {state.replace('_', ' ')}",
            details=_IDS | _STATE | _COUNTS,
            danger=state == "failed",
        )
        for state in (
            "queued",
            "started",
            "waiting_for_input",
            "waiting_for_approval",
            "resumed",
            "completed",
            "failed",
            "cancellation_requested",
            "cancelled",
        )
    },
    "agent.input.requested": _definition(
        TimelineCategory.AGENT,
        "Agent requested user input",
        details=_IDS | _STATE,
    ),
    "agent.input.received": _definition(
        TimelineCategory.AGENT,
        "Agent received user input",
        details=_IDS | _STATE,
    ),
    **{
        f"agent.tool.{state}": _definition(
            TimelineCategory.TOOL,
            f"Tool {state}",
            details=_IDS | frozenset({"tool_name"}),
            danger=state == "failed",
        )
        for state in ("started", "completed", "failed")
    },
    "agent.handoff.completed": _definition(
        TimelineCategory.TOOL,
        "Agent handoff completed",
        details=_IDS | _STATE,
    ),
    "knowledge.file.accepted": _definition(
        TimelineCategory.FILE,
        "File accepted",
        details=_IDS | frozenset({"byte_size"}),
    ),
    **{
        f"knowledge.ingestion.{state}": _definition(
            TimelineCategory.FILE,
            f"File ingestion {state}",
            details=_IDS | _STATE,
            danger=state == "failed",
        )
        for state in ("queued", "started", "completed", "failed", "cancelled")
    },
    "voice.session.started": _definition(
        TimelineCategory.VOICE,
        "Voice session started",
        details=_IDS | _STATE | _COUNTS,
    ),
    "voice.session.ended": _definition(
        TimelineCategory.VOICE,
        "Voice session ended",
        details=_IDS | _STATE | _COUNTS,
    ),
    "voice.user.interrupted_agent": _definition(
        TimelineCategory.VOICE,
        "User interrupted Agent speech",
        details=_IDS,
    ),
    **{
        f"voice.recording.{state}": _definition(
            TimelineCategory.VOICE,
            f"Recording {state}",
            details=_IDS | _STATE,
            danger=state == "failed",
        )
        for state in ("queued", "available", "failed")
    },
    **{
        f"telephony.call.{state}": _definition(
            TimelineCategory.TELEPHONY,
            f"Call {state}",
            details=_IDS | _STATE | _COUNTS,
            danger=state == "failed",
        )
        for state in (
            "started",
            "ringing",
            "answered",
            "status_changed",
            "transferred",
            "ended",
        )
    },
    **{
        f"transport.websocket.{state}": _definition(
            TimelineCategory.TECHNICAL,
            f"WebSocket {state}",
            details=_STATE | _COUNTS,
            technical=True,
            danger=state == "failed",
        )
        for state in ("connected", "disconnected", "failed")
    },
    **{
        f"transport.webrtc.{state}": _definition(
            TimelineCategory.TECHNICAL,
            f"WebRTC {state}",
            details=frozenset({"negotiation_id"}),
            technical=True,
            danger=state == "failed",
        )
        for state in ("connecting", "connected", "disconnected", "failed")
    },
    **{
        f"provider.{kind}.{state}": _definition(
            TimelineCategory.TECHNICAL,
            f"{kind.upper()} provider {state}",
            details=_STATE,
            technical=True,
            danger=state == "failed",
        )
        for kind in ("stt", "tts", "realtime")
        for state in ("connected", "disconnected", "failed")
    },
}

ALLOWED_TIMELINE_EVENT_TYPES = frozenset(TIMELINE_EVENT_CATALOG)
TECHNICAL_TIMELINE_EVENT_TYPES = frozenset(
    event_type
    for event_type, definition in TIMELINE_EVENT_CATALOG.items()
    if definition.technical
)


def event_types_for_categories(
    categories: set[TimelineCategory],
) -> frozenset[str]:
    if not categories:
        return ALLOWED_TIMELINE_EVENT_TYPES
    return frozenset(
        event_type
        for event_type, definition in TIMELINE_EVENT_CATALOG.items()
        if definition.category in categories
    )


def project_timeline_event(row: EventOutboxModel) -> UserSessionTimelineEventRead:
    definition = TIMELINE_EVENT_CATALOG[row.event_type]
    payload = row.payload if isinstance(row.payload, dict) else {}
    details = {
        key: value
        for key, value in payload.items()
        if key in definition.detail_keys
        and (value is None or isinstance(value, (str, int, float, bool)))
    }
    label = definition.label
    severity = definition.severity
    if row.event_type in {"voice.session.ended", "telephony.call.ended"} and (
        str(payload.get("status", "")).lower() == "failed"
    ):
        label = label.removesuffix("ended") + "failed"
        severity = TimelineSeverity.DANGER
    return UserSessionTimelineEventRead(
        id=row.id,
        category=definition.category,
        event_type=row.event_type,
        label=label,
        severity=severity,
        technical=definition.technical,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        causation_id=row.causation_id,
        details=details,
    )


__all__ = [
    "ALLOWED_TIMELINE_EVENT_TYPES",
    "TECHNICAL_TIMELINE_EVENT_TYPES",
    "TIMELINE_EVENT_CATALOG",
    "event_types_for_categories",
    "project_timeline_event",
]
