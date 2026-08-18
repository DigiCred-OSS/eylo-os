"""Data contracts for the `conversations` domain."""

from datetime import datetime
from typing import Any, Optional, Self
from uuid import UUID

from pydantic import Field, model_validator

from eylo.common.schemas import EyloBaseApiSchema, PaginatedResponseSchema
from eylo.modules.conversations.models.conversations import (
    ConversationChannels,
    ConversationStatus,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageContentType,
    MessageRequestFeedback,
)
from eylo.modules.conversations.schemas.participants import ParticipantKind

# ====================== Summary Schemas (Denormalized) ======================


class ContactSummary(EyloBaseApiSchema):
    """Lightweight contact representation for aggregates."""

    id: UUID
    name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None


class AgentSummary(EyloBaseApiSchema):
    """Lightweight agent representation for aggregates."""

    id: UUID
    name: str
    slug: str
    status: str


class MessageSummary(EyloBaseApiSchema):
    """Lightweight message representation for aggregates."""

    id: UUID
    kind: str
    content_kind: MessageContentKind
    content: MessageContentType
    sender_participant_id: UUID
    sender_kind: Optional[ParticipantKind] = None  # Denormalized from participant
    request_id: Optional[UUID] = None
    request_feedback: Optional[MessageRequestFeedback] = None
    created_at: datetime
    html_content: Optional[str] = None

    @model_validator(mode="after")
    def set_html_content(self) -> Self:
        """Generate HTML content from markdown content."""
        if self.content is not None:
            self.html_content = self.content.to_html_content()
        return self


class ParticipantSummary(EyloBaseApiSchema):
    """Participant with resolved entity information."""

    id: UUID
    entity_kind: ParticipantKind
    entity_id: str
    has_initiated: bool
    is_active: bool
    is_primary: bool
    joined_at: datetime
    left_at: Optional[datetime] = None
    # Denormalized entity info
    entity_name: Optional[str] = None  # Contact name or Agent name


# ====================== Aggregate Schemas ======================


class ConversationAggregateResponse(EyloBaseApiSchema):
    """API response for a single aggregated conversation.

    Exposed to frontend clients. Includes all related data in one response.
    Also used internally in service layer (replaces ConversationAggregateInDb).
    """

    # Core conversation fields
    id: UUID
    organization_id: UUID
    external_id: Optional[str] = None
    channel: ConversationChannels
    status: ConversationStatus
    title: Optional[str] = None
    has_triggered_title_generation: bool = False
    ended_at: Optional[datetime] = None
    swarm_id: UUID | None = None
    swarm_revision: int | None = None
    meta: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    # Denormalized relationships
    contact: Optional[ContactSummary] = None
    primary_agent: Optional[AgentSummary] = None
    all_agents: list[AgentSummary] = Field(default_factory=list)
    participants: list[ParticipantSummary] = Field(default_factory=list)
    messages: list[MessageSummary] = Field(default_factory=list)
    message_count: int = 0
    unread_count: int = Field(default=0, ge=0)


class ConversationAggregateBulkRequest(EyloBaseApiSchema):
    """Request schema for bulk conversation aggregation."""

    conversation_ids: list[UUID] = Field(
        ...,
        description="List of conversation IDs to aggregate",
        max_length=100,
    )
    include_messages: bool = Field(
        default=True,
        description="Include messages in response",
    )
    message_limit: Optional[int] = Field(
        default=50,
        description="Maximum number of messages per conversation",
        ge=1,
        le=500,
    )
    include_participants: bool = Field(
        default=True,
        description="Include participants in response",
    )


class ConversationAggregateBulkResponse(EyloBaseApiSchema):
    """Response schema for bulk conversation aggregation."""

    conversations: list[ConversationAggregateResponse]
    total: int


class PaginatedConversationAggregateResponse(PaginatedResponseSchema):
    """Paginated response for conversation aggregates."""

    items: list[ConversationAggregateResponse]
