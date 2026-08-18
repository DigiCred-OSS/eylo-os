"""Typed contracts for conversation request queue policy decisions."""

from enum import Enum
from uuid import UUID

from eylo.common.schemas import EyloBaseSchema
from eylo.modules.conversations.schemas.messages import MessageInDb, RequestStatus


class RequestQueuePolicyMode(str, Enum):
    """Policy used to select the next pending user request for a conversation."""

    FIFO = "FIFO"
    FILO = "FILO"
    LATEST_ONLY = "LATEST_ONLY"
    REJECT_WHILE_BUSY = "REJECT_WHILE_BUSY"


class RequestQueueDecision(EyloBaseSchema):
    """Result of applying a request queue policy to a conversation."""

    conversation_id: UUID
    policy_mode: RequestQueuePolicyMode
    next_message: MessageInDb | None
    pending_count: int
    interrupted_request_ids: tuple[UUID, ...] = ()


class RequestQueueBusyDecision(EyloBaseSchema):
    """Result of applying queue policy to a request that arrived while busy."""

    conversation_id: UUID
    policy_mode: RequestQueuePolicyMode
    request_id: UUID | None
    rejected: bool
    current_status: RequestStatus | None
