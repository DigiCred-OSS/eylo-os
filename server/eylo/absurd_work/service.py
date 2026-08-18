"""Product-state transitions for rows executed by exact Absurd tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work.model import TERMINAL_STATES, DurableState


class DurableWorkNotFound(Exception):
    """The IDs in an Absurd task do not resolve to an owned product row."""


class DurableWorkBindingPending(Exception):
    """Absurd claimed work before its product task binding became visible."""


class DurableWorkConflict(Exception):
    """A product row cannot accept the requested lifecycle transition."""


class AbsurdBoundWorkService:
    """Lock and project product lifecycle while Absurd owns execution."""

    def __init__(self, model: type[Any], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
        for_update: bool = False,
    ) -> Any:
        query = select(self.model).where(
            self.model.id == work_id,
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            raise DurableWorkNotFound
        return row

    async def begin_attempt(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
    ) -> Any:
        row = await self.get(
            work_id=work_id,
            organization_id=organization_id,
            for_update=True,
        )
        if row.state in TERMINAL_STATES:
            return row
        if row.absurd_task_id is None:
            raise DurableWorkBindingPending(
                "Absurd product task binding is not visible yet."
            )
        if row.state not in {DurableState.PENDING, DurableState.RUNNING}:
            raise DurableWorkConflict(
                f"A {row.state.value} product row cannot begin an attempt."
            )
        row.state = DurableState.RUNNING
        row.attempts += 1
        row.started_at = row.started_at or datetime.now(timezone.utc)
        await self.session.flush()
        return row

    async def bind_task(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
        task_id: UUID,
    ) -> tuple[bool, bool]:
        row = await self.get(
            work_id=work_id,
            organization_id=organization_id,
            for_update=True,
        )
        if row.absurd_task_id is not None:
            if row.absurd_task_id != task_id:
                raise DurableWorkConflict(
                    "Product work is already bound to another Absurd task."
                )
            return False, row.state is DurableState.CANCELLED
        if row.state not in {DurableState.PENDING, DurableState.CANCELLED}:
            raise DurableWorkConflict(
                f"A {row.state.value} product row cannot bind an Absurd task."
            )
        row.absurd_task_id = task_id
        await self.session.flush()
        return True, row.state is DurableState.CANCELLED

    async def succeed(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
        values: dict[str, Any] | None = None,
    ) -> Any:
        row = await self.get(
            work_id=work_id,
            organization_id=organization_id,
            for_update=True,
        )
        if row.state is DurableState.SUCCEEDED:
            return row
        if row.state is not DurableState.RUNNING:
            return row
        for key, value in (values or {}).items():
            if not hasattr(row, key):
                raise DurableWorkConflict(f"Unknown product result field {key}.")
            setattr(row, key, value)
        row.state = DurableState.SUCCEEDED
        row.last_error = None
        row.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return row

    async def fail(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
        error: str,
        permanent: bool,
    ) -> DurableState:
        row = await self.get(
            work_id=work_id,
            organization_id=organization_id,
            for_update=True,
        )
        if row.state in TERMINAL_STATES:
            return row.state
        if row.state is not DurableState.RUNNING:
            raise DurableWorkConflict(
                f"A {row.state.value} product row cannot record failure."
            )
        exhausted = permanent or row.attempts >= row.max_attempts
        row.state = DurableState.FAILED if exhausted else DurableState.PENDING
        row.last_error = error[:2000]
        if exhausted:
            row.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return row.state

    async def cancel(
        self,
        *,
        work_id: UUID,
        organization_id: UUID,
    ) -> tuple[bool, UUID | None]:
        row = await self.get(
            work_id=work_id,
            organization_id=organization_id,
            for_update=True,
        )
        if row.state in TERMINAL_STATES:
            return False, row.absurd_task_id
        row.state = DurableState.CANCELLED
        row.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True, row.absurd_task_id
