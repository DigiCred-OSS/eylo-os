"""Scheduler persistence in Postgres, claimed with SKIP LOCKED.

**This store persists and claims. It does not compute.** `next_at` arrives
already calculated by `recurrence.py` — timezone correctness and misfire policy
have to be identical whoever holds the row, so a vendor that computed its own
would make "every morning at 9" depend on where the schedule happened to live.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy import text as sql
from sqlalchemy.exc import IntegrityError

from eylo.common.contracts.scheduler import (
    ScheduleSpec,
    SchedulerCapabilities,
    SchedulerError,
)
from eylo.common.revisions import DefinitionLifecycle, RevisionConflictError
from eylo.modules.scheduler.domain import ScheduleConflictError, ScheduleNotFound
from eylo.modules.scheduler.models import ScheduleModel, ScheduleRevisionModel

logger = logging.getLogger(__name__)

PROVIDER = "postgres"


class PostgresSchedulerStore:
    """Schedule storage on the platform's own database."""

    def __init__(self, session_factory) -> None:
        # A factory rather than a session: claiming runs on a worker poll and
        # registration runs on a request, and they must not share a
        # transaction.
        self._session_factory = session_factory

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> SchedulerCapabilities:
        return SchedulerCapabilities(
            # The platform computes occurrences; this vendor stores the answer.
            native_recurrence=False,
            push_delivery=False,
            updatable=True,
            max_schedules=None,
        )

    async def register(
        self,
        spec: ScheduleSpec,
        *,
        organization_id: UUID | None = None,
        name: str | None = None,
        next_at: datetime | None = None,
        agent_id: UUID,
        agent_revision: int | None = None,
        published_by: UUID | None = None,
    ) -> str:
        """Publish revision 1 for a new stable key and return its id.

        Re-registering a key is a typed conflict. An operator must issue an
        expected-revision update so semantic movement is explicit and audited.
        """
        if organization_id is None:
            raise SchedulerError(
                "A schedule must belong to an organization.", vendor=PROVIDER
            )
        async with self._session_factory() as session:
            pinned_agent_revision = await self._resolve_agent_revision(
                session,
                organization_id=organization_id,
                agent_id=agent_id,
                agent_revision=agent_revision,
            )
            schedule = ScheduleModel(
                organization_id=organization_id,
                key=spec.key,
                name=name or spec.key,
                published_revision=1,
                lifecycle=DefinitionLifecycle.PUBLISHED.value,
                agent_id=agent_id,
                agent_revision=pinned_agent_revision,
                rule=spec.recurrence.rule,
                timezone=spec.recurrence.timezone,
                starts_at=spec.recurrence.starts_at,
                ends_at=spec.recurrence.ends_at,
                action=spec.action,
                payload=dict(spec.payload or {}),
                misfire_policy=spec.misfire_policy,
                enabled=spec.enabled,
                next_at=next_at,
            )
            session.add(schedule)
            try:
                await session.flush()
                session.add(
                    self._revision_from_schedule(
                        schedule,
                        revision=1,
                        published_by=published_by,
                    )
                )
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ScheduleConflictError(
                    "A schedule with this stable key already exists. "
                    "Use the explicit expected-revision update command."
                ) from error
            return str(schedule.id)

    async def update(
        self,
        vendor_id: str,
        spec: ScheduleSpec,
        *,
        organization_id: UUID,
        expected_revision: int,
        name: str,
        next_at: datetime,
        agent_id: UUID,
        agent_revision: int | None = None,
        published_by: UUID | None = None,
    ) -> int:
        """Append one immutable revision after optimistic locking."""
        async with self._session_factory() as session:
            schedule = await session.scalar(
                select(ScheduleModel)
                .where(
                    ScheduleModel.id == UUID(vendor_id),
                    ScheduleModel.organization_id == organization_id,
                    ScheduleModel.deleted.is_(False),
                )
                .with_for_update()
            )
            if schedule is None:
                raise ScheduleNotFound(f"No schedule {vendor_id}.")
            if schedule.published_revision != expected_revision:
                raise RevisionConflictError(
                    expected=expected_revision,
                    actual=schedule.published_revision,
                )
            pinned_agent_revision = await self._resolve_agent_revision(
                session,
                organization_id=organization_id,
                agent_id=agent_id,
                agent_revision=agent_revision,
            )
            revision = schedule.published_revision + 1
            schedule.name = name
            schedule.rule = spec.recurrence.rule
            schedule.timezone = spec.recurrence.timezone
            schedule.starts_at = spec.recurrence.starts_at
            schedule.ends_at = spec.recurrence.ends_at
            schedule.action = spec.action
            schedule.payload = dict(spec.payload or {})
            schedule.misfire_policy = spec.misfire_policy
            schedule.enabled = spec.enabled
            schedule.next_at = next_at
            schedule.retired_at = None
            schedule.last_error = None
            schedule.agent_id = agent_id
            schedule.agent_revision = pinned_agent_revision
            schedule.lifecycle = DefinitionLifecycle.PUBLISHED.value
            schedule.published_revision = revision
            session.add(
                self._revision_from_schedule(
                    schedule,
                    revision=revision,
                    published_by=published_by,
                )
            )
            await session.commit()
            return revision

    async def unregister(self, vendor_id: str) -> bool:
        """Retire a schedule. Soft, so its run history stays readable.

        True when it is gone or was already gone — the state the caller asked
        for either way, which is what makes a retry after a partial failure
        safe.
        """
        async with self._session_factory() as session:
            await session.execute(
                sql(
                    """
                    UPDATE scheduler_schedules
                    SET enabled = false, next_at = NULL, deleted = true,
                        lifecycle = 'withdrawn',
                        updated_at = now()
                    WHERE id = CAST(:id AS uuid)
                    """
                ),
                {"id": vendor_id},
            )
            await session.commit()
            return True

    async def claim_due(
        self, *, now: datetime, limit: int = 10
    ) -> list[tuple[str, int, datetime]]:
        """Take schedules whose next occurrence has arrived."""
        async with self._session_factory() as session:
            rows = await session.execute(
                sql(
                    """
                    UPDATE scheduler_schedules
                    SET next_at = NULL, updated_at = now()
                    WHERE id IN (
                        SELECT id FROM scheduler_schedules
                        WHERE enabled IS TRUE
                          AND deleted IS FALSE
                          AND next_at IS NOT NULL
                          AND next_at <= :now
                        ORDER BY next_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                    )
                    RETURNING id, published_revision, :now AS fire_at
                    """
                ),
                {"now": now, "limit": limit},
            )
            claimed = [
                (str(row.id), row.published_revision, now) for row in rows
            ]
            await session.commit()
            return claimed

    async def mark_fired(
        self,
        vendor_id: str,
        *,
        expected_revision: int,
        fired_at: datetime,
        next_at: datetime | None,
    ) -> bool:
        """Record that an occurrence was dispatched and when the next one is.

        `next_at=None` **retires** the schedule — stamping `retired_at` rather
        than deleting it, so what ran stays readable and, more importantly, so
        the recovery sweep can tell a finished schedule from one whose worker
        died mid-claim. Both look like `next_at IS NULL` and only one of them
        should be resurrected.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sql(
                    """
                    UPDATE scheduler_schedules
                    SET last_fired_at = :fired_at, next_at = :next_at,
                        retired_at = CASE WHEN CAST(:next_at AS timestamptz) IS NULL
                                          THEN now() ELSE NULL END,
                        last_error = NULL, updated_at = now()
                    WHERE id = CAST(:id AS uuid)
                      AND published_revision = :expected_revision
                    """
                ),
                {
                    "id": vendor_id,
                    "expected_revision": expected_revision,
                    "fired_at": fired_at,
                    "next_at": next_at,
                },
            )
            await session.commit()
            return bool(result.rowcount)

    async def mark_stalled(
        self, vendor_id: str, expected_revision: int, error: str
    ) -> None:
        """Record why a schedule produced no run, and leave it enabled.

        A schedule whose action was removed in a deploy, or whose rule stopped
        parsing, keeps its place. Disabling it here would mean a deploy
        silently deleting an operator's recurring job, and re-enabling it later
        would be a support ticket rather than a fix.
        """
        async with self._session_factory() as session:
            await session.execute(
                sql(
                    """
                    UPDATE scheduler_schedules
                    SET last_error = :error, updated_at = now()
                    WHERE id = CAST(:id AS uuid)
                      AND published_revision = :expected_revision
                    """
                ),
                {
                    "id": vendor_id,
                    "expected_revision": expected_revision,
                    "error": error[:2000],
                },
            )
            await session.commit()

    async def stranded(self, *, limit: int = 100) -> list[tuple[str, int]]:
        """Schedules claimed but never dispatched, so their `next_at` is lost.

        The recovery half of `claim_due`. A worker that claimed a schedule and
        died before creating its run left `next_at` NULL, which makes that
        schedule invisible to every future poll — a recurring job that stops
        forever with no error anywhere, which is the worst failure a scheduler
        has.

        `retired_at IS NULL` is what separates these from schedules that
        legitimately ran out of future. Without that column the two are
        indistinguishable, and a sweeper would either resurrect finished
        schedules or abandon stranded ones.
        """
        async with self._session_factory() as session:
            rows = await session.execute(
                sql(
                    """
                    SELECT id, published_revision FROM scheduler_schedules
                    WHERE enabled IS TRUE AND deleted IS FALSE
                      AND next_at IS NULL AND retired_at IS NULL
                    ORDER BY updated_at
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            return [(str(row.id), row.published_revision) for row in rows]

    @staticmethod
    async def _resolve_agent_revision(
        session,
        *,
        organization_id: UUID,
        agent_id: UUID,
        agent_revision: int | None,
    ) -> int:
        from eylo.modules.agents.services.revisions import AgentRevisionService

        revisions = AgentRevisionService(session)
        if agent_revision is None:
            row = await revisions.resolve_for_new_work(
                organization_id=organization_id,
                agent_id=agent_id,
                for_update=True,
            )
        else:
            row = await revisions.get_revision(
                organization_id=organization_id,
                agent_id=agent_id,
                revision=agent_revision,
                for_update=True,
            )
        return row.revision

    @staticmethod
    def _revision_from_schedule(
        schedule: ScheduleModel,
        *,
        revision: int,
        published_by: UUID | None,
    ) -> ScheduleRevisionModel:
        return ScheduleRevisionModel(
            organization_id=schedule.organization_id,
            schedule_id=schedule.id,
            revision=revision,
            name=schedule.name,
            rule=schedule.rule,
            timezone=schedule.timezone,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
            action=schedule.action,
            payload=dict(schedule.payload or {}),
            misfire_policy=schedule.misfire_policy,
            enabled=schedule.enabled,
            agent_id=schedule.agent_id,
            agent_revision=schedule.agent_revision,
            published_by=published_by,
        )
