"""Turn due schedules into immutable origins for durable AgentRuns.

The scheduler decides only that an occurrence arrived. It atomically files the
occurrence and one exact-revision AgentRun, then asks Absurd to execute that
run. The agent loop decides which allowed tools or sandbox steps are needed.

The database uniqueness on ``(schedule_id, scheduled_for)`` proves one
occurrence. The unique AgentRun origin proves one agent execution for it.
Absurd alone owns claims, retries, heartbeats and cancellation.
"""

from __future__ import annotations

import json
import logging

import arrow
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from eylo.common.contracts.scheduler import InvalidRecurrence, Recurrence
from eylo.common.database import async_session_factory, start_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import (
    AgentRunLifecycle,
    AgentRunOriginKind,
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
)
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.agent_runs.service import file_schedule_agent_run_in_transaction
from eylo.modules.scheduler.models import (
    ScheduleModel,
    ScheduleRevisionModel,
    ScheduleRunModel,
)
from eylo.modules.scheduler.persistence import PostgresSchedulerStore
from eylo.modules.scheduler.recurrence import next_occurrence, resolve_due

logger = logging.getLogger(__name__)

# How many schedules one poll will claim. Bounded so a backlog is worked
# through over several ticks rather than in one transaction.
DISPATCH_BATCH = 25
SPAWN_BATCH = 100


def _adapter() -> PostgresSchedulerStore:
    return PostgresSchedulerStore(async_session_factory)


async def dispatch_due_schedules() -> dict:
    """Turn every arrived occurrence into a run. Executes nothing."""
    now = arrow.utcnow().datetime
    adapter = _adapter()
    claimed = await adapter.claim_due(now=now, limit=DISPATCH_BATCH)
    if not claimed:
        spawned, spawn_failed = await _spawn_unbound_schedule_agent_runs()
        return {
            "claimed": 0,
            "created": 0,
            "spawned": spawned,
            "spawn_failed": spawn_failed,
        }

    created = 0
    for schedule_id, schedule_revision, fire_at in claimed:
        created += await _dispatch_one(
            adapter,
            schedule_id,
            schedule_revision,
            fire_at,
        )

    spawned, spawn_failed = await _spawn_unbound_schedule_agent_runs()
    return {
        "claimed": len(claimed),
        "created": created,
        "spawned": spawned,
        "spawn_failed": spawn_failed,
    }


async def _dispatch_one(
    adapter,
    schedule_id: str,
    schedule_revision: int,
    now,
) -> int:
    """File occurrences against the revision captured by the due claim."""
    async with start_transaction() as session:
        schedule = await session.get(ScheduleModel, schedule_id)
        if schedule is None:
            return 0
        definition = await session.scalar(
            select(ScheduleRevisionModel).where(
                ScheduleRevisionModel.organization_id == schedule.organization_id,
                ScheduleRevisionModel.schedule_id == schedule.id,
                ScheduleRevisionModel.revision == schedule_revision,
            )
        )
        if definition is None or definition.availability != "published":
            await adapter.mark_stalled(
                schedule_id,
                schedule_revision,
                "Pinned schedule revision is unavailable.",
            )
            return 0
        recurrence = Recurrence(
            rule=definition.rule,
            timezone=definition.timezone,
            starts_at=definition.starts_at,
            ends_at=definition.ends_at,
        )
        organization_id = schedule.organization_id
        action, payload = definition.action, dict(definition.payload or {})
        policy = definition.misfire_policy
        agent_id = definition.agent_id
        agent_revision = definition.agent_revision
        principal = InitiatingPrincipalRef(
            organization_id=organization_id,
            kind=(
                InitiatingPrincipalKind.MEMBER
                if definition.published_by is not None
                else InitiatingPrincipalKind.WORKER
            ),
            principal_id=definition.published_by or definition.agent_id,
        )
        last_fired_at = schedule.last_fired_at

    try:
        resolution = resolve_due(
            recurrence, last_fired_at=last_fired_at, now=now, policy=policy
        )
    except (InvalidRecurrence, ValueError) as error:
        # A rule that stopped resolving keeps its schedule. Disabling here
        # would mean a bad edit silently deleting a recurring job.
        await adapter.mark_stalled(
            schedule_id,
            schedule_revision,
            "Schedule recurrence could not be resolved.",
        )
        logger.warning(
            "Schedule=%s could not resolve error_type=%s",
            schedule_id,
            type(error).__name__,
        )
        return 0

    if not resolution.fire_at:
        # Claimed but nothing owed — a schedule whose `next_at` was stale.
        # Restoring it is what keeps it visible to the next poll.
        await adapter.mark_fired(
            schedule_id,
            expected_revision=schedule_revision,
            fired_at=last_fired_at or now,
            next_at=resolution.next_at or next_occurrence(recurrence, after=now),
        )
        return 0

    created = 0
    for index, moment in enumerate(resolution.fire_at):
        async with start_transaction() as session:
            run = ScheduleRunModel(
                organization_id=organization_id,
                schedule_id=schedule_id,
                schedule_revision=schedule_revision,
                agent_id=agent_id,
                agent_revision=agent_revision,
                scheduled_for=moment,
                action=action,
                payload=payload,
                # Only the first run of a coalesced batch carries the skip
                # count; attributing it to all of them would multiply it.
                misfired_count=resolution.skipped if index == 0 else 0,
            )
            try:
                async with session.begin_nested():
                    session.add(run)
                    await session.flush()
                    await file_schedule_agent_run_in_transaction(
                        session,
                        organization_id=organization_id,
                        schedule_run_id=run.id,
                        principal=principal,
                        agent_id=agent_id,
                        agent_revision=agent_revision,
                        goal=_schedule_goal(action, payload),
                        context_manifest=_schedule_context_manifest(run),
                    )
                created += 1
            except IntegrityError as error:
                if not _is_occurrence_conflict(error):
                    raise
                # Another worker already created this occurrence. That is the
                # unique constraint doing its job, not an error — the
                # occurrence exists exactly once and someone will run it.
                logger.info(
                    "Occurrence %s of schedule %s already exists.", moment, schedule_id
                )

    await adapter.mark_fired(
        schedule_id,
        expected_revision=schedule_revision,
        fired_at=resolution.fire_at[-1],
        next_at=resolution.next_at,
    )
    if resolution.skipped:
        # INFO rather than silence: an operator whose scheduler was down
        # deserves to see what it cost.
        logger.info(
            "Schedule %s coalesced %d missed occurrence(s).",
            schedule_id,
            resolution.skipped,
        )
    return created


def _is_occurrence_conflict(error: IntegrityError) -> bool:
    return _integrity_constraint_name(error) == "uq_scheduler_runs_schedule_occurrence"


def _integrity_constraint_name(error: IntegrityError) -> str | None:
    """Read a constraint name across psycopg and asyncpg wrapper shapes."""
    pending: list[object] = [error, error.orig]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))

        diagnostic = getattr(current, "diag", None)
        name = getattr(diagnostic, "constraint_name", None) or getattr(
            current,
            "constraint_name",
            None,
        )
        if isinstance(name, str):
            return name

        for attribute in ("__cause__", "__context__"):
            chained = getattr(current, attribute, None)
            if chained is not None:
                pending.append(chained)
    return None


async def recover_stranded_schedules() -> dict:
    """Recover schedules claimed before their occurrence transaction committed."""
    # A worker that claimed a schedule and died before creating its run left
    # `next_at` NULL, so that schedule is invisible to every future poll — a
    # recurring job that stops forever with nothing anywhere saying so.
    adapter = _adapter()
    restored = 0
    for schedule_id, schedule_revision in await adapter.stranded():
        async with start_transaction() as session:
            schedule = await session.get(ScheduleModel, schedule_id)
            if schedule is None:
                continue
            definition = await session.scalar(
                select(ScheduleRevisionModel).where(
                    ScheduleRevisionModel.organization_id == schedule.organization_id,
                    ScheduleRevisionModel.schedule_id == schedule.id,
                    ScheduleRevisionModel.revision == schedule_revision,
                    ScheduleRevisionModel.availability == "published",
                )
            )
            if definition is None:
                continue
        restored += await _dispatch_one(
            adapter,
            schedule_id,
            schedule_revision,
            arrow.utcnow().datetime,
        )
    spawned, spawn_failed = await _spawn_unbound_schedule_agent_runs()
    if restored:
        logger.warning(
            "Restored %d schedule(s) stranded by a worker that died mid-claim.",
            restored,
        )
    return {
        "occurrences_restored": restored,
        "spawned": spawned,
        "spawn_failed": spawn_failed,
    }


def _schedule_goal(action: str, payload: dict) -> str:
    encoded_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        "Execute this scheduled task using your allowed capabilities. "
        "Decide which tools or sandbox steps are needed.\n"
        f"Task: {action}\nInputs: {encoded_payload}"
    )


def _schedule_context_manifest(run: ScheduleRunModel) -> dict:
    return {
        "schedule_id": str(run.schedule_id),
        "schedule_revision": run.schedule_revision,
        "schedule_run_id": str(run.id),
        "scheduled_for": run.scheduled_for.isoformat(),
        "action": run.action,
        "payload": dict(run.payload or {}),
        "misfired_count": run.misfired_count,
    }


async def _spawn_unbound_schedule_agent_runs() -> tuple[int, int]:
    async with start_transaction(ro=True) as session:
        rows = await session.execute(
            select(AgentRunModel.organization_id, AgentRunModel.id)
            .where(
                AgentRunModel.origin_kind == AgentRunOriginKind.SCHEDULE_OCCURRENCE,
                AgentRunModel.lifecycle == AgentRunLifecycle.QUEUED,
                AgentRunModel.absurd_task_id.is_(None),
                AgentRunModel.deleted.is_(False),
            )
            .order_by(AgentRunModel.created_at, AgentRunModel.id)
            .limit(SPAWN_BATCH)
        )
        pending = list(rows.all())

    spawned = 0
    failed = 0
    for organization_id, run_id in pending:
        try:
            await spawn_agent_run(
                organization_id=organization_id,
                run_id=run_id,
            )
            spawned += 1
        except Exception as error:  # noqa: BLE001 - next poll retries this DB row
            failed += 1
            logger.error(
                "Could not spawn scheduled AgentRun=%s error_type=%s",
                run_id,
                type(error).__name__,
            )
    return spawned, failed
