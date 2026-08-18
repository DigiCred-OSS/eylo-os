"""Target-authoritative filing of asynchronous Eylo deletion requests."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.durable_runtime import DURABLE_MAX_ATTEMPTS
from eylo.modules.contacts.domain import ContactNotFound
from eylo.modules.contacts.schemas.indb import ContactRef
from eylo.modules.contacts.service import ContactService
from eylo.modules.deletions.domain import (
    DeletionTargetNotFound,
    DeletionTargetType,
)
from eylo.modules.deletions.models import DeletionJobModel
from eylo.modules.deletions.schemas import DeletionJobApiResponse
from eylo.modules.deletions.service import DeletionJobService
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.pipelines.deletions.durable_execution import spawn_deletion

logger = logging.getLogger(__name__)


class DeletionRequestUseCase:
    """Resolve exact target ownership, file once, then nudge the DB outbox."""

    async def request_contact(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        requested_by_member_id: UUID,
    ) -> DeletionJobApiResponse:
        async with start_transaction() as session:
            jobs = DeletionJobService(session)
            existing = await jobs.get_for_target(
                organization_id=organization_id,
                target_type=DeletionTargetType.CONTACT,
                target_id=contact_id,
                for_update=True,
            )
            if existing is not None:
                job = existing
            else:
                try:
                    await ContactService().request_deletion(
                        ContactRef(
                            organization_id=organization_id,
                            contact_id=contact_id,
                        ),
                        actor_member_id=requested_by_member_id,
                    )
                except ContactNotFound:
                    raise DeletionTargetNotFound from None
                job = await jobs.file_request(
                    organization_id=organization_id,
                    target_type=DeletionTargetType.CONTACT,
                    target_id=contact_id,
                    requested_by_member_id=requested_by_member_id,
                    max_attempts=DURABLE_MAX_ATTEMPTS,
                )
            response = DeletionJobApiResponse.from_record(job)
        await _nudge(job)
        return response

    async def request_call(
        self,
        *,
        organization_id: UUID,
        call_id: UUID,
        requested_by_member_id: UUID,
    ) -> DeletionJobApiResponse:
        async with start_transaction() as session:
            jobs = DeletionJobService(session)
            existing = await jobs.get_for_target(
                organization_id=organization_id,
                target_type=DeletionTargetType.CALL,
                target_id=call_id,
                for_update=True,
            )
            if existing is not None:
                job = existing
            else:
                call = await session.scalar(
                    select(TelephonyCallModel.id)
                    .where(
                        TelephonyCallModel.id == call_id,
                        TelephonyCallModel.organization_id == organization_id,
                        TelephonyCallModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
                if call is None:
                    raise DeletionTargetNotFound
                job = await jobs.file_request(
                    organization_id=organization_id,
                    target_type=DeletionTargetType.CALL,
                    target_id=call_id,
                    requested_by_member_id=requested_by_member_id,
                    max_attempts=DURABLE_MAX_ATTEMPTS,
                )
            response = DeletionJobApiResponse.from_record(job)
        await _nudge(job)
        return response


async def _nudge(job: DeletionJobModel) -> None:
    if job.absurd_task_id is not None:
        return
    try:
        await spawn_deletion(
            organization_id=job.organization_id,
            job_id=job.id,
        )
    except Exception as error:  # noqa: BLE001 - committed outbox is recoverable
        logger.warning(
            "Could not immediately spawn deletion job: %s",
            type(error).__name__,
        )


__all__ = ["DeletionRequestUseCase"]
