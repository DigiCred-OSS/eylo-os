"""Data contracts for the `conversations` domain."""

import datetime
from enum import Enum
from uuid import UUID

from eylo.common.schemas import EyloBaseSchema


class ConversationRuntimePhase(str, Enum):
    """Shared runtime processing phase for a conversation."""

    PROCESSING = "PROCESSING"
    DRAINING = "DRAINING"


class ConversationRuntimeReleaseDecision(str, Enum):
    """Owner-checked release outcome for a conversation runtime status."""

    RELEASED = "RELEASED"
    CONTINUE = "CONTINUE"
    LOST = "LOST"


class ConversationRuntimeClaimResult(EyloBaseSchema):
    """Owner-claim result, including abandoned active request details if stale."""

    acquired: bool
    stale_takeover: bool = False
    previous_active_request_id: UUID | None = None
    previous_active_user_message_id: UUID | None = None


class ConversationRuntimeStatus(EyloBaseSchema):
    """Redis-backed runtime status for one active conversation processor."""

    organization_id: UUID
    conversation_id: UUID
    owner_token: str
    phase: ConversationRuntimePhase
    started_at: datetime.datetime
    heartbeat_at: datetime.datetime
    expires_at: datetime.datetime
    heartbeat_epoch: float | None = None
    expires_epoch: float | None = None
    active_request_id: UUID | None = None
    active_user_message_id: UUID | None = None
    wake_requested: bool = False
    pending_count: int = 0
    last_enqueued_request_id: UUID | None = None
    last_enqueued_user_message_id: UUID | None = None
