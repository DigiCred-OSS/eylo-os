"""Tenant-scoped persistence and lifecycle for deletion jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionJobConflict,
    DeletionJobNotFound,
    DeletionJobStatus,
    DeletionTargetType,
)
from eylo.modules.deletions.models import DeletionJobModel
from eylo.modules.members.models import MemberModel


class DeletionJobService:
    """Own job identity, tenant authority, and durable product transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        for_update: bool = False,
    ) -> DeletionJobModel:
        query = select(DeletionJobModel).where(
            DeletionJobModel.id == job_id,
            DeletionJobModel.organization_id == organization_id,
            DeletionJobModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        if row is None:
            raise DeletionJobNotFound
        return row

    async def get_for_target(
        self,
        *,
        organization_id: UUID,
        target_type: DeletionTargetType,
        target_id: UUID,
        for_update: bool = False,
    ) -> DeletionJobModel | None:
        query = select(DeletionJobModel).where(
            DeletionJobModel.organization_id == organization_id,
            DeletionJobModel.target_type == target_type,
            DeletionJobModel.target_id == target_id,
            DeletionJobModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return await self._session.scalar(query)

    async def file_request(
        self,
        *,
        organization_id: UUID,
        target_type: DeletionTargetType,
        target_id: UUID,
        requested_by_member_id: UUID,
        max_attempts: int,
    ) -> DeletionJobModel:
        """Create or return the one tombstone for this exact owned target."""
        if max_attempts <= 0:
            raise ValueError("Deletion max attempts must be positive.")
        member_exists = await self._session.scalar(
            select(MemberModel.id).where(
                MemberModel.id == requested_by_member_id,
                MemberModel.organization_id == organization_id,
                MemberModel.deleted.is_(False),
            )
        )
        if member_exists is None:
            raise DeletionJobNotFound

        existing = await self.get_for_target(
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            for_update=True,
        )
        if existing is not None:
            return existing

        job_id = uuid4()
        result = await self._session.execute(
            insert(DeletionJobModel)
            .values(
                id=job_id,
                external_id=str(uuid4()),
                organization_id=organization_id,
                target_type=target_type,
                target_id=target_id,
                requested_by_member_id=requested_by_member_id,
                status=DeletionJobStatus.PENDING,
                max_attempts=max_attempts,
                deleted=False,
            )
            .on_conflict_do_nothing(
                constraint="uq_deletion_jobs_target",
            )
            .returning(DeletionJobModel.id)
        )
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            return await self.get(
                organization_id=organization_id,
                job_id=inserted_id,
                for_update=True,
            )
        existing = await self.get_for_target(
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            for_update=True,
        )
        if existing is None:
            raise DeletionJobConflict("Deletion request race did not converge.")
        return existing

    async def bind_task(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        task_id: UUID,
    ) -> DeletionJobModel:
        row = await self.get(
            organization_id=organization_id,
            job_id=job_id,
            for_update=True,
        )
        if row.absurd_task_id is not None:
            if row.absurd_task_id != task_id:
                raise DeletionJobConflict(
                    "Deletion job is bound to another durable task."
                )
            return row
        if row.status is not DeletionJobStatus.PENDING:
            raise DeletionJobConflict(
                "Only pending deletion jobs can bind durable execution."
            )
        row.absurd_task_id = task_id
        await self._session.flush()
        return row

    async def begin_attempt(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> DeletionJobModel:
        row = await self.get(
            organization_id=organization_id,
            job_id=job_id,
            for_update=True,
        )
        if row.status in {DeletionJobStatus.SUCCEEDED, DeletionJobStatus.FAILED}:
            return row
        if row.absurd_task_id is None:
            raise DeletionJobConflict("Deletion durable task is not bound.")
        if row.status not in {
            DeletionJobStatus.PENDING,
            DeletionJobStatus.RUNNING,
        }:
            raise DeletionJobConflict("Deletion job cannot begin an attempt.")
        if row.status is DeletionJobStatus.PENDING:
            row.status = DeletionJobStatus.RUNNING
            row.attempts += 1
            row.started_at = row.started_at or datetime.now(timezone.utc)
        await self._session.flush()
        return row

    async def succeed(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> DeletionJobModel:
        row = await self.get(
            organization_id=organization_id,
            job_id=job_id,
            for_update=True,
        )
        if row.status is DeletionJobStatus.SUCCEEDED:
            return row
        if row.status is not DeletionJobStatus.RUNNING:
            return row
        row.status = DeletionJobStatus.SUCCEEDED
        row.error_code = None
        row.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row

    async def fail(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        error_code: DeletionErrorCode,
        retryable: bool,
    ) -> DeletionJobModel:
        row = await self.get(
            organization_id=organization_id,
            job_id=job_id,
            for_update=True,
        )
        if row.status in {DeletionJobStatus.SUCCEEDED, DeletionJobStatus.FAILED}:
            return row
        if row.status is not DeletionJobStatus.RUNNING:
            raise DeletionJobConflict("Deletion job cannot record a failure.")
        exhausted = not retryable or row.attempts >= row.max_attempts
        row.status = (
            DeletionJobStatus.FAILED if exhausted else DeletionJobStatus.PENDING
        )
        row.error_code = error_code
        if exhausted:
            row.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row


__all__ = ["DeletionJobService"]
