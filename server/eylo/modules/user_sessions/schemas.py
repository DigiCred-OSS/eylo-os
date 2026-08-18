"""Private API projections for user sessions and their safe timelines."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, JsonValue

from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.user_sessions.domain import (
    UserSessionEntryChannel,
    UserSessionState,
)


class TimelineCategory(StrEnum):
    SESSION = "session"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    AGENT = "agent"
    TOOL = "tool"
    FILE = "file"
    VOICE = "voice"
    TELEPHONY = "telephony"
    TECHNICAL = "technical"


class TimelineSeverity(StrEnum):
    DEFAULT = "default"
    DANGER = "danger"


class UserSessionContactRead(EyloBaseApiSchema):
    id: UUID
    name: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None


class UserSessionCountsRead(EyloBaseApiSchema):
    conversations: int = 0
    messages: int = 0
    agent_runs: int = 0
    voice_sessions: int = 0
    telephony_calls: int = 0
    timeline_events: int = 0


class UserSessionRead(EyloBaseApiSchema):
    id: UUID
    organization_id: UUID
    contact: UserSessionContactRead
    entry_channel: UserSessionEntryChannel
    state: UserSessionState
    connection_sequence: int
    started_at: datetime
    last_activity_at: datetime
    disconnected_at: datetime | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    counts: UserSessionCountsRead


class UserSessionPage(EyloBaseApiSchema):
    items: list[UserSessionRead]
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class UserSessionTimelineEventRead(EyloBaseApiSchema):
    id: UUID
    category: TimelineCategory
    event_type: str
    label: str
    severity: TimelineSeverity
    technical: bool
    subject_type: str
    subject_id: UUID
    occurred_at: datetime
    recorded_at: datetime
    causation_id: UUID | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class UserSessionTimelinePage(EyloBaseApiSchema):
    items: list[UserSessionTimelineEventRead]
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


__all__ = [
    "TimelineCategory",
    "TimelineSeverity",
    "UserSessionContactRead",
    "UserSessionCountsRead",
    "UserSessionPage",
    "UserSessionRead",
    "UserSessionTimelineEventRead",
    "UserSessionTimelinePage",
]
