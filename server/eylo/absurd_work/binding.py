"""Bind organization-owned product rows to exact Absurd tasks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from eylo.absurd_work.model import DurableState
from eylo.absurd_work.service import AbsurdBoundWorkService, DurableWorkConflict
from eylo.common.database import start_transaction
from eylo.durable_runtime import PlatformDurableRuntime


async def spawn_bound_work(
    *,
    model: type[Any],
    organization_id: UUID,
    work_id: UUID,
    workflow_name: str,
    params_name: str,
    idempotency_prefix: str,
) -> UUID:
    """Idempotently spawn and bind one already-committed product row."""
    async with start_transaction(ro=True) as session:
        row = await AbsurdBoundWorkService(model, session).get(
            work_id=work_id,
            organization_id=organization_id,
        )
        if row.absurd_task_id is not None:
            return row.absurd_task_id
        if row.state is not DurableState.PENDING:
            raise DurableWorkConflict(
                f"A {row.state.value} product row cannot be spawned."
            )
        max_attempts = row.max_attempts

    runtime = PlatformDurableRuntime()
    try:
        task_id = await runtime.spawn_task(
            name=workflow_name,
            params={
                "organization_id": str(organization_id),
                params_name: str(work_id),
            },
            idempotency_key=f"{idempotency_prefix}:v1:{organization_id}:{work_id}",
            max_attempts=max_attempts,
        )
        async with start_transaction() as session:
            _, cancellation_pending = await AbsurdBoundWorkService(
                model,
                session,
            ).bind_task(
                work_id=work_id,
                organization_id=organization_id,
                task_id=task_id,
            )
        if cancellation_pending:
            await runtime.cancel_task(task_id)
        return task_id
    finally:
        await runtime.close()


async def spawn_unbound_work(
    *,
    model: type[Any],
    spawn: Callable[[UUID, UUID], Awaitable[UUID]],
    limit: int = 100,
) -> tuple[int, list[tuple[UUID, Exception]]]:
    """Repeat producer spawn from DB outbox rows without executing product work."""
    async with start_transaction(ro=True) as session:
        rows = list(
            (
                await session.execute(
                    select(model.organization_id, model.id)
                    .where(
                        model.state == DurableState.PENDING,
                        model.absurd_task_id.is_(None),
                        model.deleted.is_(False),
                    )
                    .order_by(model.created_at.asc())
                    .limit(limit)
                )
            ).all()
        )
    spawned = 0
    failures: list[tuple[UUID, Exception]] = []
    for organization_id, work_id in rows:
        try:
            await spawn(organization_id, work_id)
            spawned += 1
        except DurableWorkConflict:
            continue
        except Exception as error:  # noqa: BLE001 - report independent failure
            failures.append((work_id, error))
    return spawned, failures


async def cancel_bound_work(
    *,
    model: type[Any],
    organization_id: UUID,
    work_id: UUID,
) -> bool:
    """Commit product cancellation before notifying the exact Absurd task."""
    async with start_transaction() as session:
        cancelled, task_id = await AbsurdBoundWorkService(model, session).cancel(
            work_id=work_id,
            organization_id=organization_id,
        )
    if cancelled and task_id is not None:
        runtime = PlatformDurableRuntime()
        try:
            await runtime.cancel_task(task_id)
        finally:
            await runtime.close()
    return cancelled
