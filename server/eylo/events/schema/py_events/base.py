"""Typed contracts for best-effort in-process events."""

import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from eylo.common.identifiers import normalize_uuid_like
from eylo.modules.conversations.schemas.conversations import ConversationInDb
from eylo.modules.conversations.schemas.messages import MessageInDb
from eylo.modules.conversations.schemas.participants import ParticipantInDb


class BaseEvent(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def normalize_uuid_fields(cls, value):
        return normalize_uuid_like(value)


class ConversationEvent(BaseEvent):
    conversation_id: UUID
    organization_id: UUID
    conversation: ConversationInDb


class ConversationCreatedEvent(ConversationEvent):
    pass


class MessageCreatedEvent(BaseEvent):
    conversation_id: UUID
    message_id: UUID
    message: MessageInDb


class ParticipantCreatedEvent(BaseEvent):
    conversation_id: UUID
    participant_id: UUID
    participant: ParticipantInDb


class AgentLifecycleOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class AgentLifecycleEvent(BaseEvent):
    """Bounded, correlated UI projection of one agent run stage."""

    organization_id: UUID
    conversation_id: UUID
    contact_ids: tuple[UUID, ...]
    request_id: UUID
    message_id: UUID | None = None
    run_id: UUID
    run_started_at: datetime.datetime
    sequence: int = Field(ge=1)


class AgentProcessingEvent(AgentLifecycleEvent):
    """Event emitted when agent starts processing a request."""


class AgentResponseCompleteEvent(AgentLifecycleEvent):
    """Terminal UI projection for a completed or failed agent run."""

    outcome: AgentLifecycleOutcome


class AuthRequiredEvent(BaseEvent):
    """Event emitted when tool execution requires authentication."""

    conversation_id: UUID
    organization_id: UUID
    integration_id: UUID
    vendor: str
    auth_kind: str | None = None
    integration_name: str
    reason: str
    contact_id: UUID | None
    message: str


# ── Agent run lifecycle events ──
# Lossy, correlated UI projections of LLM inference and tool execution stages.


class AgentRunInferenceEvent(AgentLifecycleEvent):
    """Event that signals an LLM inference call is starting."""


class AgentRunToolEvent(AgentLifecycleEvent):
    """Event that signals a tool execution is starting."""


class AgentToolResponseEvent(AgentLifecycleEvent):
    """Event that signals a tool execution has completed."""
