"""Creating and retiring schedules.

Thin on purpose: the recurrence engine decides *when*, the vendor stores, and
this is the seam that validates before either is touched. Routes and agent
tools both come through here so neither can skip the validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic_core import to_jsonable_python
from sqlalchemy import and_, select

from eylo.common.contracts.scheduler import (
    InvalidRecurrence,
    MisfirePolicy,
    Recurrence,
    ScheduleSpec,
)
from eylo.common.database import async_session_factory
from eylo.common.revisions import DefinitionLifecycle, PublishedRevisionState
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.scheduler.actions import registered_actions
from eylo.modules.scheduler.discovery import register_scheduled_actions
from eylo.modules.scheduler.domain import ScheduleNotFound
from eylo.modules.scheduler.models import (
    ScheduleModel,
    ScheduleRevisionModel,
    ScheduleRunModel,
)
from eylo.modules.scheduler.persistence import PostgresSchedulerStore
from eylo.modules.scheduler.recurrence import next_occurrence, validate
from eylo.modules.scheduler.schemas import ScheduleRunRead

logger = logging.getLogger(__name__)

_MAX_SCHEDULE_PAYLOAD_BYTES = 12_000


def _adapter() -> PostgresSchedulerStore:
    return PostgresSchedulerStore(async_session_factory)


async def create_schedule(
    *,
    organization_id: UUID,
    key: str,
    name: str,
    action: str,
    payload: dict,
    recurrence: Recurrence,
    misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE,
    agent_id: UUID,
    agent_revision: int | None = None,
    published_by: UUID | None = None,
) -> tuple[str, datetime | None]:
    """Validate and publish a new schedule revision 1.

    Both checks happen here, before anything is written, because both produce
    errors an operator can only act on at the moment they are creating the
    thing. A schedule stored with an unknown action is one that fails a run at
    a time nobody is watching.
    """
    first = _validate_definition(
        action=action,
        payload=payload,
        recurrence=recurrence,
    )

    schedule_id = await _adapter().register(
        ScheduleSpec(
            key=key,
            recurrence=recurrence,
            action=action,
            payload=payload,
            misfire_policy=misfire_policy,
        ),
        organization_id=organization_id,
        name=name,
        next_at=first,
        agent_id=agent_id,
        agent_revision=agent_revision,
        published_by=published_by,
    )
    return schedule_id, first


async def update_schedule(
    schedule_id: UUID,
    *,
    organization_id: UUID,
    expected_revision: int,
    name: str,
    action: str,
    payload: dict,
    recurrence: Recurrence,
    misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE,
    agent_id: UUID,
    agent_revision: int | None = None,
    published_by: UUID | None = None,
) -> tuple[int, datetime]:
    """Append an explicitly requested immutable schedule definition."""
    first = _validate_definition(
        action=action,
        payload=payload,
        recurrence=recurrence,
    )
    revision = await _adapter().update(
        str(schedule_id),
        ScheduleSpec(
            key=str(schedule_id),
            recurrence=recurrence,
            action=action,
            payload=payload,
            misfire_policy=misfire_policy,
        ),
        organization_id=organization_id,
        expected_revision=expected_revision,
        name=name,
        next_at=first,
        agent_id=agent_id,
        agent_revision=agent_revision,
        published_by=published_by,
    )
    return revision, first


async def list_schedules(
    *, organization_id: UUID, agent_id: UUID | None = None, limit: int = 50
) -> list[ScheduleModel]:
    """Schedules for an organization, or for one agent within it.

    `agent_id` narrows rather than filters after the fact — passing it is how a
    caller says "only what this agent created", and an agent tool always passes
    it. An agent listing its organization's schedules would be an agent
    learning about work it has no business cancelling.
    """
    async with async_session_factory() as session:
        query = select(ScheduleModel).where(
            ScheduleModel.organization_id == organization_id,
            ScheduleModel.deleted.is_(False),
        )
        if agent_id is not None:
            query = query.where(ScheduleModel.agent_id == agent_id)
        query = query.order_by(ScheduleModel.next_at.asc().nullslast()).limit(limit)
        return list((await session.execute(query)).scalars().all())


async def get_schedule(
    schedule_id: UUID, *, organization_id: UUID, agent_id: UUID | None = None
) -> ScheduleModel:
    """One schedule, always filtered by scope rather than fetched then checked.

    A fetch-then-check leaks existence through whichever error the check
    forgets to raise, and through timing.
    """
    async with async_session_factory() as session:
        query = select(ScheduleModel).where(
            ScheduleModel.id == schedule_id,
            ScheduleModel.organization_id == organization_id,
            ScheduleModel.deleted.is_(False),
        )
        if agent_id is not None:
            query = query.where(ScheduleModel.agent_id == agent_id)
        schedule = (await session.execute(query)).scalar_one_or_none()
        if schedule is None:
            raise ScheduleNotFound(f"No schedule {schedule_id}.")
        return schedule


async def cancel_schedule(
    schedule_id: UUID, *, organization_id: UUID, agent_id: UUID | None = None
) -> bool:
    """Retire a schedule. Its run history stays readable.

    Scoped the same way as reading it: an agent may only cancel what it
    created, which is what `agent_id` on the row exists to make enforceable.
    """
    await get_schedule(schedule_id, organization_id=organization_id, agent_id=agent_id)
    return await _adapter().unregister(str(schedule_id))


async def revoke_schedule_revision(
    schedule_id: UUID,
    revision: int,
    *,
    organization_id: UUID,
    actor_id: UUID,
    reason: str,
) -> ScheduleRevisionModel:
    """Emergency-revoke one exact revision and request filed-work cancellation."""
    cancellations: list[tuple[UUID, UUID]] = []
    async with async_session_factory() as session:
        async with session.begin():
            schedule = await session.scalar(
                select(ScheduleModel)
                .where(
                    ScheduleModel.id == schedule_id,
                    ScheduleModel.organization_id == organization_id,
                    ScheduleModel.deleted.is_(False),
                )
                .with_for_update()
            )
            row = await session.scalar(
                select(ScheduleRevisionModel)
                .where(
                    ScheduleRevisionModel.schedule_id == schedule_id,
                    ScheduleRevisionModel.organization_id == organization_id,
                    ScheduleRevisionModel.revision == revision,
                )
                .with_for_update()
            )
            if schedule is None or row is None:
                raise ScheduleNotFound("Schedule revision not found.")
            revoked = PublishedRevisionState(
                availability=row.availability,
                published_at=row.published_at,
                revoked_at=row.revoked_at,
                revoked_by=row.revoked_by,
                revocation_reason=row.revocation_reason,
                cancellation_requested_at=row.cancellation_requested_at,
            ).revoke(
                actor_id=actor_id,
                reason=reason,
                at=datetime.now(timezone.utc),
            )
            row.availability = revoked.availability.value
            row.revoked_at = revoked.revoked_at
            row.revoked_by = revoked.revoked_by
            row.revocation_reason = revoked.revocation_reason
            row.cancellation_requested_at = revoked.cancellation_requested_at
            if schedule.published_revision == revision:
                schedule.lifecycle = DefinitionLifecycle.WITHDRAWN.value
                schedule.enabled = False
                schedule.next_at = None
            run_ids = list(
                (
                    await session.scalars(
                        select(AgentRunModel.id)
                        .join(
                            ScheduleRunModel,
                            and_(
                                ScheduleRunModel.id
                                == AgentRunModel.origin_schedule_run_id,
                                ScheduleRunModel.organization_id
                                == AgentRunModel.organization_id,
                            ),
                        )
                        .where(
                            ScheduleRunModel.organization_id == organization_id,
                            ScheduleRunModel.schedule_id == schedule_id,
                            ScheduleRunModel.schedule_revision == revision,
                            AgentRunModel.deleted.is_(False),
                        )
                    )
                ).all()
            )
            from eylo.modules.agent_runs.service import (
                request_agent_run_cancellation_in_transaction,
            )

            for run_id in run_ids:
                task_id = await request_agent_run_cancellation_in_transaction(
                    session,
                    organization_id=organization_id,
                    run_id=run_id,
                )
                if task_id is not None:
                    cancellations.append((run_id, task_id))
            await session.flush()
            revoked_row = row

    if cancellations:
        from eylo.modules.agent_runs.absurd import cancel_bound_agent_run

        for run_id, task_id in cancellations:
            await cancel_bound_agent_run(
                organization_id=organization_id,
                run_id=run_id,
                task_id=task_id,
            )
    return revoked_row


async def list_runs(
    schedule_id: UUID, *, organization_id: UUID, limit: int = 50
) -> list[ScheduleRunRead]:
    """Recent runs of one schedule, newest first."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ScheduleRunModel, AgentRunModel)
            .join(
                AgentRunModel,
                and_(
                    AgentRunModel.origin_schedule_run_id == ScheduleRunModel.id,
                    AgentRunModel.organization_id
                    == ScheduleRunModel.organization_id,
                    AgentRunModel.deleted.is_(False),
                ),
            )
            .where(
                ScheduleRunModel.schedule_id == schedule_id,
                ScheduleRunModel.organization_id == organization_id,
            )
            .order_by(ScheduleRunModel.scheduled_for.desc())
            .limit(limit)
        )
        return [
            ScheduleRunRead(
                id=occurrence.id,
                schedule_id=occurrence.schedule_id,
                schedule_revision=occurrence.schedule_revision,
                agent_id=occurrence.agent_id,
                agent_revision=occurrence.agent_revision,
                scheduled_for=occurrence.scheduled_for,
                action=occurrence.action,
                agent_run_id=run.id,
                lifecycle=run.lifecycle,
                outcome=run.outcome,
                misfired_count=occurrence.misfired_count,
                started_at=run.started_at,
                finished_at=run.finished_at,
                result=run.result,
                failure_summary=run.failure_summary,
            )
            for occurrence, run in result.all()
        ]


def _validate_definition(
    *,
    action: str,
    payload: dict,
    recurrence: Recurrence,
) -> datetime:
    validate(recurrence)
    register_scheduled_actions()
    if action not in registered_actions():
        raise InvalidRecurrence(
            f"No handler is registered for action '{action}'. "
            f"Available: {', '.join(registered_actions()) or 'none'}."
        )
    normalized_payload = to_jsonable_python(payload)
    if not isinstance(normalized_payload, dict):
        raise InvalidRecurrence("A schedule payload must be a JSON object.")
    payload_size = len(
        json.dumps(
            normalized_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    if payload_size > _MAX_SCHEDULE_PAYLOAD_BYTES:
        raise InvalidRecurrence(
            f"A schedule payload may contain at most {_MAX_SCHEDULE_PAYLOAD_BYTES} "
            "encoded bytes."
        )
    first = next_occurrence(
        recurrence, after=recurrence.starts_at - timedelta(microseconds=1)
    )
    if first is None:
        raise InvalidRecurrence(
            "That recurrence has no occurrence in the future; nothing would run."
        )
    return first


__all__ = [
    "ScheduleNotFound",
    "cancel_schedule",
    "create_schedule",
    "get_schedule",
    "list_runs",
    "list_schedules",
    "revoke_schedule_revision",
    "update_schedule",
]
