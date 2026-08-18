"""SQLAlchemy model for canonical conversation messages and request state."""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloBaseModel
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageKind,
    MessageRequestFeedback,
    RequestStatus,
)


class MessagesModel(EyloBaseModel):
    """Represents a message in a conversation.

    This class defines the structure and properties of a conversation message,
    including its content, metadata, and references to other entities.
    """

    __tablename__ = "conversation_messages"

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_conversation_messages_user_session_conversation",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "agent_run_id IS NULL OR kind IN "
            "('ASSISTANT', 'TOOL_USE', 'TOOL_RESULT') OR "
            "(kind = 'SYSTEM' AND content_kind = 'TASK_RESULT')",
            name="ck_conversation_messages_agent_run_output_kind",
        ),
        Index(
            "uq_conversation_messages_task_result_agent_run",
            "agent_run_id",
            unique=True,
            postgresql_where=text(
                "kind = 'SYSTEM' AND content_kind = 'TASK_RESULT' "
                "AND deleted IS FALSE"
            ),
        ),
    )

    kind: Mapped[MessageKind] = mapped_column(Text, nullable=False)
    content_kind: Mapped[MessageContentKind] = mapped_column(Text, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parent_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_messages.id"), nullable=True
    )
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    request_status: Mapped[Optional[RequestStatus]] = mapped_column(Text, nullable=True)
    request_feedback: Mapped[Optional[MessageRequestFeedback]] = mapped_column(
        Text, nullable=True
    )
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    external_id = mapped_column(String(320), nullable=True, unique=False, index=True)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_conversations.id"),
        nullable=False,
        index=True,
    )
    user_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    sender_participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_participants.id"),
        nullable=False,
        index=True,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
