"""Data contracts for the `conversations` domain."""

import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

import arrow
from pydantic import Field, field_validator

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseModelSchema,
    EyloBaseSchema,
    PaginatedResponseSchema,
)

# ====================== Enums ======================


class ParticipantKind(str, Enum):
    """Enum for participant types."""

    AGENT = "AGENT"
    CONTACT = "CONTACT"
    MEMBER = "MEMBER"


# ====================== Participant Schemas ======================


class ParticipantBaseSchema(EyloBaseModelSchema):
    conversation_id: UUID
    entity_kind: ParticipantKind
    entity_id: str
    agent_id: UUID | None = None
    agent_revision: int | None = Field(default=None, gt=0)
    has_initiated: bool = False
    added_by_kind: Optional[ParticipantKind] = None
    added_by_id: Optional[str] = None
    joined_at: Optional[datetime.datetime] = None
    is_active: bool = True
    removed_by_kind: Optional[ParticipantKind] = None
    removed_by_id: Optional[str] = None
    left_at: Optional[datetime.datetime] = None
    last_read_at: Optional[datetime.datetime] = None
    is_primary: bool = False


class ParticipantCreateSchema(EyloBaseSchema):
    conversation_id: UUID
    entity_kind: ParticipantKind
    entity_id: str | UUID
    agent_id: UUID | None = None
    agent_revision: int | None = Field(default=None, gt=0)
    has_initiated: bool = False
    joined_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime
    )
    is_primary: bool = False

    @field_validator("entity_id", mode="after")
    @classmethod
    def entity_id_to_str(cls, entity_id: str | UUID) -> str:
        if isinstance(entity_id, UUID):
            return str(entity_id)
        return entity_id

    @field_validator("agent_revision", mode="after")
    @classmethod
    def exact_agent_ref(cls, agent_revision: int | None, info):
        is_agent = info.data.get("entity_kind") == ParticipantKind.AGENT
        agent_id = info.data.get("agent_id")
        if is_agent and (agent_id is None or agent_revision is None):
            raise ValueError("Agent participants require an exact agent revision.")
        if not is_agent and (agent_id is not None or agent_revision is not None):
            raise ValueError("Only agent participants can reference an agent revision.")
        return agent_revision


class ParticipantUpdateSchema(EyloBaseSchema):
    added_by_kind: Optional[ParticipantKind] = None
    added_by_id: Optional[str] = None
    is_active: Optional[bool] = False
    removed_by_kind: Optional[ParticipantKind] = None
    removed_by_id: Optional[str] = None
    left_at: Optional[datetime.datetime] = None
    is_primary: Optional[bool] = None


class ParticipantInDb(ParticipantBaseSchema):
    class Config:
        from_attributes = True


# ====================== API Response ======================


class ParticipantApiResponseSchema(ParticipantInDb, EyloBaseApiSchema):
    pass


class ConversationParticipantsPaginated(PaginatedResponseSchema):
    """Paginated list of participants for a conversation."""

    data: List[ParticipantApiResponseSchema]
