"""Member API projection of content-free deletion jobs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import ConfigDict

from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionJobStatus,
    DeletionTargetType,
)

if TYPE_CHECKING:
    from eylo.modules.deletions.models import DeletionJobModel

_STATUS_MESSAGES = {
    DeletionJobStatus.PENDING: "Deletion from Eylo is pending.",
    DeletionJobStatus.RUNNING: "Deletion from Eylo is in progress.",
    DeletionJobStatus.SUCCEEDED: "Deleted from Eylo.",
    DeletionJobStatus.FAILED: "Deletion from Eylo failed.",
}


class DeletionJobApiResponse(EyloBaseApiSchema):
    """An asynchronous deletion monitor; it makes no provider-side claim."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    target_type: DeletionTargetType
    target_id: UUID
    requested_by_member_id: UUID
    status: DeletionJobStatus
    error_code: DeletionErrorCode | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status_url: str
    message: str

    @classmethod
    def from_record(cls, record: "DeletionJobModel") -> "DeletionJobApiResponse":
        return cls(
            id=record.id,
            target_type=record.target_type,
            target_id=record.target_id,
            requested_by_member_id=record.requested_by_member_id,
            status=record.status,
            error_code=record.error_code,
            requested_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            status_url=f"/api/deletions/{record.id}",
            message=_STATUS_MESSAGES[record.status],
        )


__all__ = ["DeletionJobApiResponse"]
