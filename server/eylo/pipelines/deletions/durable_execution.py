"""Absurd binding and product-state projection for explicit deletion."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask, SuspendTask
from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.durable_runtime import PlatformDurableRuntime
from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionExecutionFailure,
    DeletionJobConflict,
    DeletionJobStatus,
)
from eylo.modules.deletions.models import DeletionJobModel
from eylo.modules.deletions.service import DeletionJobService
from eylo.pipelines.deletions.erasure import erase_deletion_target

logger = logging.getLogger(__name__)

DELETION_WORKFLOW = "eylo.deletion.execute.v1"


def register_deletion_workflow(runtime: PlatformDurableRuntime) -> None:
    runtime.register_task(
        name=DELETION_WORKFLOW,
        handler=DeletionWorkflow().execute,
    )


async def spawn_deletion(*, organization_id: UUID, job_id: UUID) -> UUID:
    """Idempotently bind one committed deletion tombstone to Absurd."""
    async with start_transaction(ro=True) as session:
        row = await DeletionJobService(session).get(
            organization_id=organization_id,
            job_id=job_id,
        )
        if row.absurd_task_id is not None:
            return row.absurd_task_id
        if row.status is not DeletionJobStatus.PENDING:
            raise DeletionJobConflict("Only pending deletion jobs can be spawned.")
        max_attempts = row.max_attempts

    runtime = PlatformDurableRuntime()
    try:
        task_id = await runtime.spawn_task(
            name=DELETION_WORKFLOW,
            params={
                "organization_id": str(organization_id),
                "job_id": str(job_id),
            },
            idempotency_key=f"deletion:v1:{organization_id}:{job_id}",
            max_attempts=max_attempts,
        )
        async with start_transaction() as session:
            await DeletionJobService(session).bind_task(
                organization_id=organization_id,
                job_id=job_id,
                task_id=task_id,
            )
        return task_id
    finally:
        await runtime.close()


async def spawn_unbound_deletions(*, limit: int = 100) -> int:
    """Repeat producer binding from DB outbox rows; never claim product work."""
    async with start_transaction(ro=True) as session:
        rows = list(
            (
                await session.execute(
                    select(DeletionJobModel.organization_id, DeletionJobModel.id)
                    .where(
                        DeletionJobModel.status == DeletionJobStatus.PENDING,
                        DeletionJobModel.absurd_task_id.is_(None),
                        DeletionJobModel.deleted.is_(False),
                    )
                    .order_by(DeletionJobModel.created_at.asc())
                    .limit(limit)
                )
            ).all()
        )
    spawned = 0
    for organization_id, job_id in rows:
        try:
            await spawn_deletion(
                organization_id=organization_id,
                job_id=job_id,
            )
            spawned += 1
        except DeletionJobConflict:
            continue
        except Exception as error:  # noqa: BLE001 - jobs remain in the DB outbox
            logger.error(
                "Could not spawn deletion work: %s",
                type(error).__name__,
            )
    return spawned


class DeletionWorkflow:
    """Execute one organization-owned deletion and project bounded status."""

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, job_id = _parse_params(params)
        async with start_transaction() as session:
            job = await DeletionJobService(session).begin_attempt(
                organization_id=organization_id,
                job_id=job_id,
            )
            if job.status in {DeletionJobStatus.SUCCEEDED, DeletionJobStatus.FAILED}:
                return _receipt(job)

        try:
            await erase_deletion_target(job, task_context)
        except (CancelledTask, SuspendTask):
            raise
        except DeletionExecutionFailure as error:
            return await _record_failure(
                organization_id=organization_id,
                job_id=job_id,
                error_code=error.code,
                retryable=error.retryable,
            )
        except Exception as error:  # noqa: BLE001 - product state records safe code
            logger.warning("Deletion execution failed with %s", type(error).__name__)
            return await _record_failure(
                organization_id=organization_id,
                job_id=job_id,
                error_code=DeletionErrorCode.INTERNAL_FAILURE,
                retryable=True,
            )

        async with start_transaction() as session:
            row = await DeletionJobService(session).succeed(
                organization_id=organization_id,
                job_id=job_id,
            )
            return _receipt(row)


async def _record_failure(
    *,
    organization_id: UUID,
    job_id: UUID,
    error_code: DeletionErrorCode,
    retryable: bool,
) -> dict[str, Any]:
    async with start_transaction() as session:
        row = await DeletionJobService(session).fail(
            organization_id=organization_id,
            job_id=job_id,
            error_code=error_code,
            retryable=retryable,
        )
        receipt = _receipt(row)
    if row.status is DeletionJobStatus.PENDING:
        raise DeletionExecutionFailure(error_code, retryable=True)
    return receipt


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "job_id"}:
        raise ValueError("Deletion task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["job_id"]))
    except (TypeError, ValueError):
        raise ValueError("Deletion task params contain an invalid UUID.") from None


def _receipt(job: DeletionJobModel) -> dict[str, Any]:
    return {
        "organization_id": str(job.organization_id),
        "job_id": str(job.id),
        "target_type": job.target_type.value,
        "status": job.status.value,
        "error_code": None if job.error_code is None else job.error_code.value,
    }


__all__ = [
    "DELETION_WORKFLOW",
    "DeletionWorkflow",
    "register_deletion_workflow",
    "spawn_deletion",
    "spawn_unbound_deletions",
]
