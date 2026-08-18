"""Content-free audit tombstones for organization-requested deletion."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel
from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionJobStatus,
    DeletionTargetType,
)


def _enum(enum_type, name: str):
    return ENUM(
        enum_type,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


class DeletionJobModel(EyloOrganizationModel):
    """Durable execution authority and surviving content-free audit fact."""

    __tablename__ = "deletion_jobs"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "target_type",
            "target_id",
            name="uq_deletion_jobs_target",
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0",
            name="ck_deletion_jobs_attempts",
        ),
        CheckConstraint(
            "(status IN ('pending', 'running') AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_deletion_jobs_terminal_time",
        ),
        CheckConstraint(
            "status <> 'running' OR started_at IS NOT NULL",
            name="ck_deletion_jobs_running_started",
        ),
        CheckConstraint(
            "status = 'pending' OR absurd_task_id IS NOT NULL",
            name="ck_deletion_jobs_bound_before_execution",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR error_code IS NULL",
            name="ck_deletion_jobs_success_has_no_error",
        ),
        CheckConstraint(
            "status <> 'failed' OR error_code IS NOT NULL",
            name="ck_deletion_jobs_failure_has_error",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    target_type: Mapped[DeletionTargetType] = mapped_column(
        _enum(DeletionTargetType, "deletion_target_type_enum"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    requested_by_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeletionJobStatus] = mapped_column(
        _enum(DeletionJobStatus, "deletion_job_status_enum"),
        nullable=False,
        default=DeletionJobStatus.PENDING,
        server_default=DeletionJobStatus.PENDING.value,
        index=True,
    )
    error_code: Mapped[DeletionErrorCode | None] = mapped_column(
        _enum(DeletionErrorCode, "deletion_error_code_enum"),
        nullable=True,
    )
    absurd_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        unique=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


__all__ = ["DeletionJobModel"]
