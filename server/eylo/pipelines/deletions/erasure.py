"""Target dispatch boundary filled by the call/contact erasure slices."""

from __future__ import annotations

from absurd_sdk import AsyncTaskContext

from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionExecutionFailure,
    DeletionTargetType,
)
from eylo.pipelines.deletions.call_erasure import erase_call
from eylo.pipelines.deletions.contact_erasure import erase_contact


async def erase_deletion_target(job, task_context: AsyncTaskContext) -> None:
    """Dispatch one target without allowing the scheduler to choose behavior."""
    if job.target_type is DeletionTargetType.CALL:
        await erase_call(
            organization_id=job.organization_id,
            call_id=job.target_id,
            task_context=task_context,
        )
        return
    if job.target_type is DeletionTargetType.CONTACT:
        await erase_contact(
            organization_id=job.organization_id,
            contact_id=job.target_id,
            task_context=task_context,
        )
        return
    raise DeletionExecutionFailure(
        DeletionErrorCode.INTERNAL_FAILURE,
        retryable=False,
    )


__all__ = ["erase_deletion_target"]
