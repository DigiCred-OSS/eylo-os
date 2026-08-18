"""This module defines the Conversation model for the database.

It uses SQLAlchemy ORM to map the ConversationModel class to the conversation_conversations table.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel


class ConversationChannels(str, Enum):
    """Enum for conversation channel types.

    Identifies which interface initiated the conversation.
    Used to determine available tools and response formatting.
    """

    PHONE = "PHONE"
    CHAT = "CHAT"
    WEB = "WEB"
    WIDGET = "WIDGET"
    SMS = "SMS"
    API = "API"


class ConversationStatus(str, Enum):
    """Enum for conversation status."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class ConversationsModel(EyloOrganizationModel):
    """Represents a conversation in the system.

    This class defines the structure and properties of a conversation,
    including its metadata, timestamps, and references to other entities.
    """

    __tablename__ = "conversation_conversations"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_conversation_conversations_id_organization",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["swarm_id", "swarm_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_conversation_conversations_swarm_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(swarm_id IS NULL AND swarm_revision IS NULL) OR "
            "(swarm_id IS NOT NULL AND swarm_revision > 0)",
            name="ck_conversation_conversations_swarm_ref",
        ),
    )

    channel: Mapped[ConversationChannels] = mapped_column(
        ENUM(ConversationChannels, name="conversation_channel_enum"),
        nullable=False,
        default=ConversationChannels.CHAT,
        server_default=ConversationChannels.CHAT,
        doc="Channel of the conversation.",
    )
    status: Mapped[ConversationStatus] = mapped_column(
        ENUM(ConversationStatus, name="conversation_status_enum"),
        nullable=False,
        default=ConversationStatus.ACTIVE,
        server_default=ConversationStatus.ACTIVE,
        doc="Status of the conversation.",
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    has_triggered_title_generation: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=True
    )
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    swarm_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    swarm_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
