"""SQLAlchemy model for conversation participant and read-state lifecycle."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloBaseModel
from eylo.modules.conversations.schemas.participants import ParticipantKind


class ParticipantsModel(EyloBaseModel):
    """Represents a participant in a conversation.

    This class defines the structure and properties of a conversation participant,
    including their role, reference, and timestamps.
    """

    __tablename__ = "conversation_participants"

    entity_kind: Mapped[ParticipantKind] = mapped_column(Text, nullable=False)
    # lookup into the contacts_user or agents_agent table
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    agent_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # whether the participant has initiated the conversation
    has_initiated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # the kind of participant that added this participant
    added_by_kind: Mapped[ParticipantKind] = mapped_column(Text, nullable=True)
    # the ID of the participant that added this participant
    added_by_id: Mapped[str] = mapped_column(Text, nullable=True)
    # the time the participant joined the conversation
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # whether the participant is active in the conversation
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    removed_by_kind: Mapped[Optional[ParticipantKind]] = mapped_column(
        Text, nullable=True
    )
    removed_by_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # the time the participant left the conversation
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_conversations.id"), nullable=False
    )

    # is primary
    # track the primary contact and the agent responsible for the conversation
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index("ix_participant_conversation_id", "conversation_id"),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
            ],
            name="fk_conversation_participants_agent_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(entity_kind = 'AGENT' AND agent_id IS NOT NULL "
            "AND agent_revision > 0 AND entity_id = agent_id::text) OR "
            "(entity_kind <> 'AGENT' AND agent_id IS NULL "
            "AND agent_revision IS NULL)",
            name="ck_conversation_participants_exact_agent_ref",
        ),
    )
