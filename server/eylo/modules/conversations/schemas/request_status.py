"""Data contracts for the `conversations` domain."""

from uuid import UUID

from eylo.common.schemas import EyloBaseSchema
from eylo.modules.conversations.schemas.messages import RequestStatus


class RequestStatusTransitionResult(EyloBaseSchema):
    request_id: UUID
    previous_status: RequestStatus | None
    requested_status: RequestStatus
    current_status: RequestStatus | None
    changed: bool
    valid: bool
