"""Atomic organization capacity reservations for durable executions."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.domain import (
    AgentRunLifecycle,
    ExecutionBudgetConflict,
    ExecutionBudgetDimension,
    ExecutionBudgetExceeded,
    ExecutionBudgetNotConfigured,
    ExecutionBudgetUnavailable,
    ExecutionUsageNotReported,
)
from eylo.modules.agent_runs.models import (
    AgentRunModel,
    OrganizationExecutionBudgetModel,
    OrganizationExecutionReservationModel,
)
from eylo.modules.agent_runs.schemas import (
    OrganizationExecutionBudgetRead,
    OrganizationExecutionBudgetUpsert,
)

_MICROUNITS_PER_UNIT = 1_000_000


@dataclass(frozen=True, slots=True)
class _ExecutionBudgetScope:
    organization_id: UUID
    run_id: UUID


class _MemoryExecutionKind(str, Enum):
    FORMATION = "formation"
    RECONCILIATION = "reconciliation"


@dataclass(frozen=True, slots=True)
class _MemoryExecutionBudgetScope:
    organization_id: UUID
    job_id: UUID
    kind: _MemoryExecutionKind


_current_budget_scope: ContextVar[_ExecutionBudgetScope | None] = ContextVar(
    "agent_run_execution_budget_scope",
    default=None,
)
_current_memory_budget_scope: ContextVar[_MemoryExecutionBudgetScope | None] = (
    ContextVar(
        "memory_formation_execution_budget_scope",
        default=None,
    )
)


@dataclass(frozen=True, slots=True)
class _ActiveCapacity:
    runs: int
    tokens: int
    milliseconds: int
    cost_microunits: int


@contextmanager
def agent_run_execution_budget_scope(*, organization_id: UUID, run_id: UUID):
    """Bind nested model calls to the currently executing durable run."""
    token = _current_budget_scope.set(
        _ExecutionBudgetScope(
            organization_id=organization_id,
            run_id=run_id,
        )
    )
    try:
        yield
    finally:
        _current_budget_scope.reset(token)


@contextmanager
def memory_formation_execution_budget_scope(
    *,
    organization_id: UUID,
    job_id: UUID,
):
    """Bind one extraction completion to its durable formation reservation."""
    with _memory_execution_budget_scope(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    ):
        yield


@contextmanager
def memory_reconciliation_execution_budget_scope(
    *,
    organization_id: UUID,
    job_id: UUID,
):
    """Bind one proposal completion to its durable reconciliation reservation."""
    with _memory_execution_budget_scope(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    ):
        yield


@contextmanager
def _memory_execution_budget_scope(
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
):
    token = _current_memory_budget_scope.set(
        _MemoryExecutionBudgetScope(
            organization_id=organization_id,
            job_id=job_id,
            kind=kind,
        )
    )
    try:
        yield
    finally:
        _current_memory_budget_scope.reset(token)


async def meter_current_agent_run_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    """Meter a provider response when called inside an AgentRun workflow."""
    scope = _current_budget_scope.get()
    if scope is None:
        return
    if input_tokens is None or output_tokens is None:
        raise ExecutionUsageNotReported(
            "Model provider did not report usage required by the execution budget."
        )
    await meter_agent_run_usage(
        organization_id=scope.organization_id,
        run_id=scope.run_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def meter_current_execution_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    """Meter the active AgentRun or durable Memory execution, if any."""
    memory_scope = _current_memory_budget_scope.get()
    if memory_scope is not None:
        if input_tokens is None or output_tokens is None:
            raise ExecutionUsageNotReported(
                "Model provider did not report usage required by the execution budget."
            )
        await _meter_memory_execution_usage(
            organization_id=memory_scope.organization_id,
            job_id=memory_scope.job_id,
            kind=memory_scope.kind,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return
    await meter_current_agent_run_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def finish_current_memory_formation_execution() -> None:
    """End metered formation time immediately before its atomic fact commit."""
    scope = _current_memory_budget_scope.get()
    if scope is None:
        return
    async with start_transaction() as session:
        exceeded = await release_memory_formation_reservation_in_transaction(
            session,
            organization_id=scope.organization_id,
            job_id=scope.job_id,
        )
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)


def has_current_agent_run_budget_scope() -> bool:
    """Return whether output must pass durable budget accounting first."""
    return _current_budget_scope.get() is not None


def current_agent_run_id() -> UUID | None:
    """Return the durable run owning the current execution, when one exists."""
    scope = _current_budget_scope.get()
    return None if scope is None else scope.run_id


async def get_organization_execution_budget(
    *, organization_id: UUID
) -> OrganizationExecutionBudgetRead:
    """Return the explicit policy; absence is never replaced by defaults."""
    async with start_transaction(ro=True) as session:
        row = await _get_budget(session, organization_id=organization_id)
        if row is None:
            raise ExecutionBudgetNotConfigured(
                "Organization execution budget is not configured."
            )
        return OrganizationExecutionBudgetRead.model_validate(row)


async def put_organization_execution_budget(
    *,
    organization_id: UUID,
    command: OrganizationExecutionBudgetUpsert,
) -> OrganizationExecutionBudgetRead:
    """Create or optimistically replace one organization policy."""
    async with start_transaction() as session:
        row = await _get_budget(
            session,
            organization_id=organization_id,
            for_update=True,
        )
        values = _budget_values(command)
        if row is None:
            if command.expected_state_revision is not None:
                raise ExecutionBudgetConflict(
                    "Execution budget does not exist at the expected revision."
                )
            row = OrganizationExecutionBudgetModel(
                organization_id=organization_id,
                **values,
            )
            session.add(row)
        else:
            if command.expected_state_revision != row.state_revision:
                raise ExecutionBudgetConflict(
                    "Execution budget revision is stale or missing."
                )
            active = await _load_active_reservations(
                session,
                organization_id=organization_id,
                for_update=True,
            )
            _require_capacity(
                policy=command,
                active=_measure_active_capacity(active),
                include_run=False,
            )
            for field_name, value in values.items():
                setattr(row, field_name, value)
            row.state_revision += 1

        await session.flush()
        await session.refresh(row)
        return OrganizationExecutionBudgetRead.model_validate(row)


async def reserve_agent_run_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Atomically hold the complete per-run envelope before filing succeeds."""
    policy = await _get_budget(
        session,
        organization_id=organization_id,
        for_update=True,
    )
    if policy is None:
        raise ExecutionBudgetNotConfigured(
            "Organization execution budget is not configured."
        )

    existing = await _get_reservation(
        session,
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if existing is not None:
        return existing

    active = await _load_active_reservations(
        session,
        organization_id=organization_id,
        for_update=True,
    )
    _require_capacity(
        policy=policy,
        active=_measure_active_capacity(active),
        include_run=True,
    )
    reservation = OrganizationExecutionReservationModel(
        organization_id=organization_id,
        run_id=run_id,
        budget_id=policy.id,
        budget_state_revision=policy.state_revision,
        token_limit=policy.run_token_limit,
        time_limit_milliseconds=policy.run_time_limit_milliseconds,
        cost_limit_microunits=policy.run_cost_limit_microunits,
        cost_microunits_per_million_tokens=(policy.cost_microunits_per_million_tokens),
    )
    session.add(reservation)
    await session.flush()
    return reservation


async def reserve_memory_formation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Atomically hold one complete envelope for a durable formation job."""
    return await _reserve_memory_execution_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    )


async def reserve_memory_reconciliation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Atomically hold one complete envelope for a reconciliation job."""
    return await _reserve_memory_execution_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    )


async def _reserve_memory_execution_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
) -> OrganizationExecutionReservationModel:
    policy = await _get_budget(
        session,
        organization_id=organization_id,
        for_update=True,
    )
    if policy is None:
        raise ExecutionBudgetNotConfigured(
            "Organization execution budget is not configured."
        )

    existing = await _get_memory_reservation(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=kind,
        for_update=True,
    )
    if existing is not None:
        return existing

    active = await _load_active_reservations(
        session,
        organization_id=organization_id,
        for_update=True,
    )
    _require_capacity(
        policy=policy,
        active=_measure_active_capacity(active),
        include_run=True,
    )
    reservation = OrganizationExecutionReservationModel(
        organization_id=organization_id,
        **{_memory_job_id_attribute(kind): job_id},
        budget_id=policy.id,
        budget_state_revision=policy.state_revision,
        token_limit=policy.run_token_limit,
        time_limit_milliseconds=policy.run_time_limit_milliseconds,
        cost_limit_microunits=policy.run_cost_limit_microunits,
        cost_microunits_per_million_tokens=(policy.cost_microunits_per_million_tokens),
    )
    session.add(reservation)
    await session.flush()
    return reservation


async def activate_agent_run_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Start metered time or atomically reacquire capacity after a wait."""
    policy = await _require_locked_budget(
        session,
        organization_id=organization_id,
    )
    reservation = await _require_reservation(
        session,
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    if not reservation.active:
        active = await _load_active_reservations(
            session,
            organization_id=organization_id,
            for_update=True,
        )
        _require_capacity_for_pinned_reservation(
            policy=policy,
            active=_measure_active_capacity(active),
            reservation=reservation,
        )
        reservation.active = True
        reservation.released_at = None
    if reservation.active_since is None:
        reservation.active_since = _now()
    await session.flush()
    return reservation


async def activate_memory_formation_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Start metered formation time or reacquire its pinned retry envelope."""
    return await _activate_memory_execution_reservation_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    )


async def activate_memory_reconciliation_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> OrganizationExecutionReservationModel:
    """Start metered reconciliation time or reacquire its pinned envelope."""
    return await _activate_memory_execution_reservation_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    )


async def _activate_memory_execution_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
) -> OrganizationExecutionReservationModel:
    policy = await _require_locked_budget(
        session,
        organization_id=organization_id,
    )
    reservation = await _require_memory_reservation(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=kind,
        for_update=True,
    )
    if not reservation.active:
        active = await _load_active_reservations(
            session,
            organization_id=organization_id,
            for_update=True,
        )
        _require_capacity_for_pinned_reservation(
            policy=policy,
            active=_measure_active_capacity(active),
            reservation=reservation,
        )
        reservation.active = True
        reservation.released_at = None
    if reservation.active_since is None:
        reservation.active_since = _now()
    await session.flush()
    return reservation


async def release_agent_run_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> ExecutionBudgetDimension | None:
    """Release every active dimension while retaining the usage audit."""
    reservation = await _require_reservation(
        session,
        organization_id=organization_id,
        run_id=run_id,
        for_update=True,
    )
    now = _now()
    _accrue_active_time(reservation, now=now)
    exceeded = _exceeded_dimension(reservation)
    if exceeded is not None:
        reservation.exceeded_dimension = exceeded
    if reservation.active:
        reservation.active = False
        reservation.active_since = None
        reservation.released_at = now
    await session.flush()
    return exceeded


async def release_memory_formation_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> ExecutionBudgetDimension | None:
    """Release one formation envelope while retaining its usage audit."""
    return await _release_memory_execution_reservation_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    )


async def release_memory_reconciliation_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
) -> ExecutionBudgetDimension | None:
    """Release one reconciliation envelope while retaining its usage audit."""
    return await _release_memory_execution_reservation_in_transaction(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    )


async def _release_memory_execution_reservation_in_transaction(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
) -> ExecutionBudgetDimension | None:
    reservation = await _require_memory_reservation(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=kind,
        for_update=True,
    )
    now = _now()
    _accrue_active_time(reservation, now=now)
    exceeded = _exceeded_dimension(reservation)
    if exceeded is not None:
        reservation.exceeded_dimension = exceeded
    if reservation.active:
        reservation.active = False
        reservation.active_since = None
        reservation.released_at = now
    await session.flush()
    return exceeded


async def meter_agent_run_usage(
    *,
    organization_id: UUID,
    run_id: UUID,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Commit exact normalized usage before allowing output to become canonical."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Metered token counts cannot be negative.")
    token_delta = input_tokens + output_tokens
    exceeded: ExecutionBudgetDimension | None = None
    async with start_transaction() as session:
        reservation = await _require_reservation(
            session,
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if not reservation.active:
            raise ExecutionBudgetConflict(
                "Agent run usage cannot be metered without an active reservation."
            )
        reservation.used_tokens += token_delta
        reservation.used_cost_microunits = _cost_microunits(
            tokens=reservation.used_tokens,
            rate=reservation.cost_microunits_per_million_tokens,
        )
        exceeded = _exceeded_dimension(reservation)
        if exceeded is not None:
            reservation.exceeded_dimension = exceeded
        await session.flush()
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)


async def meter_memory_formation_usage(
    *,
    organization_id: UUID,
    job_id: UUID,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Commit one idempotent extraction usage report before any fact mutation."""
    await _meter_memory_execution_usage(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def meter_memory_reconciliation_usage(
    *,
    organization_id: UUID,
    job_id: UUID,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Commit one idempotent reconciliation usage report before any effect."""
    await _meter_memory_execution_usage(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def _meter_memory_execution_usage(
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
    input_tokens: int,
    output_tokens: int,
) -> None:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Metered token counts cannot be negative.")
    token_total = input_tokens + output_tokens
    exceeded: ExecutionBudgetDimension | None = None
    async with start_transaction() as session:
        reservation = await _require_memory_reservation(
            session,
            organization_id=organization_id,
            job_id=job_id,
            kind=kind,
            for_update=True,
        )
        if not reservation.active:
            raise ExecutionBudgetConflict(
                f"{_memory_execution_label(kind)} usage requires an active reservation."
            )
        if reservation.usage_reported:
            if reservation.used_tokens != token_total:
                raise ExecutionBudgetConflict(
                    f"{_memory_execution_label(kind)} replay reported different usage."
                )
            exceeded = reservation.exceeded_dimension
        else:
            reservation.used_tokens = token_total
            reservation.used_cost_microunits = _cost_microunits(
                tokens=token_total,
                rate=reservation.cost_microunits_per_million_tokens,
            )
            reservation.usage_reported = True
            exceeded = _exceeded_dimension(reservation)
            if exceeded is not None:
                reservation.exceeded_dimension = exceeded
            await session.flush()
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)


async def check_agent_run_active_time(*, organization_id: UUID, run_id: UUID) -> int:
    """Commit elapsed active time and reject the complete run on exceedance."""
    exceeded: ExecutionBudgetDimension | None = None
    remaining_milliseconds = 0
    async with start_transaction() as session:
        reservation = await _require_reservation(
            session,
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if not reservation.active:
            lifecycle = await session.scalar(
                select(AgentRunModel.lifecycle).where(
                    AgentRunModel.id == run_id,
                    AgentRunModel.organization_id == organization_id,
                    AgentRunModel.deleted.is_(False),
                )
            )
            if lifecycle in {
                AgentRunLifecycle.WAITING_FOR_INPUT,
                AgentRunLifecycle.WAITING_FOR_APPROVAL,
                AgentRunLifecycle.COMPLETED,
                AgentRunLifecycle.FAILED,
                AgentRunLifecycle.CANCELLED,
            }:
                return 0
            raise ExecutionBudgetConflict(
                "Running AgentRun has no active execution reservation."
            )
        if reservation.active_since is None:
            raise ExecutionBudgetConflict(
                "Agent run active time cannot be metered outside execution."
            )
        _accrue_active_time(reservation, now=_now())
        exceeded = _exceeded_dimension(reservation)
        if exceeded is not None:
            reservation.exceeded_dimension = exceeded
        remaining_milliseconds = max(
            0,
            reservation.time_limit_milliseconds - reservation.active_milliseconds,
        )
        await session.flush()
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)
    return remaining_milliseconds


async def check_memory_formation_active_time(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> int:
    """Commit elapsed formation time and return its remaining milliseconds."""
    return await _check_memory_execution_active_time(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    )


async def check_memory_reconciliation_active_time(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> int:
    """Commit elapsed reconciliation time and return remaining milliseconds."""
    return await _check_memory_execution_active_time(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    )


async def _check_memory_execution_active_time(
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
) -> int:
    exceeded: ExecutionBudgetDimension | None = None
    remaining_milliseconds = 0
    async with start_transaction() as session:
        reservation = await _require_memory_reservation(
            session,
            organization_id=organization_id,
            job_id=job_id,
            kind=kind,
            for_update=True,
        )
        if not reservation.active or reservation.active_since is None:
            raise ExecutionBudgetConflict(
                f"{_memory_execution_label(kind)} has no active execution reservation."
            )
        _accrue_active_time(reservation, now=_now())
        exceeded = _exceeded_dimension(reservation)
        if exceeded is not None:
            reservation.exceeded_dimension = exceeded
        remaining_milliseconds = max(
            0,
            reservation.time_limit_milliseconds - reservation.active_milliseconds,
        )
        await session.flush()
    if exceeded is not None:
        raise ExecutionBudgetExceeded(exceeded)
    return remaining_milliseconds


async def require_memory_formation_usage_reported(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> None:
    """Reject a success projection if an adapter bypassed usage accounting."""
    await _require_memory_execution_usage_reported(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.FORMATION,
    )


async def require_memory_reconciliation_usage_reported(
    *,
    organization_id: UUID,
    job_id: UUID,
) -> None:
    """Reject a reconciliation result that bypassed usage accounting."""
    await _require_memory_execution_usage_reported(
        organization_id=organization_id,
        job_id=job_id,
        kind=_MemoryExecutionKind.RECONCILIATION,
    )


async def _require_memory_execution_usage_reported(
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
) -> None:
    async with start_transaction(ro=True) as session:
        reservation = await _require_memory_reservation(
            session,
            organization_id=organization_id,
            job_id=job_id,
            kind=kind,
            for_update=False,
        )
        if not reservation.usage_reported:
            raise ExecutionUsageNotReported(
                f"{_memory_execution_label(kind)} provider did not report usage."
            )


async def _get_budget(
    session: AsyncSession,
    *,
    organization_id: UUID,
    for_update: bool = False,
) -> OrganizationExecutionBudgetModel | None:
    query = select(OrganizationExecutionBudgetModel).where(
        OrganizationExecutionBudgetModel.organization_id == organization_id,
        OrganizationExecutionBudgetModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def _require_locked_budget(
    session: AsyncSession,
    *,
    organization_id: UUID,
) -> OrganizationExecutionBudgetModel:
    policy = await _get_budget(
        session,
        organization_id=organization_id,
        for_update=True,
    )
    if policy is None:
        raise ExecutionBudgetNotConfigured(
            "Organization execution budget is not configured."
        )
    return policy


async def _get_reservation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    for_update: bool = False,
) -> OrganizationExecutionReservationModel | None:
    query = select(OrganizationExecutionReservationModel).where(
        OrganizationExecutionReservationModel.organization_id == organization_id,
        OrganizationExecutionReservationModel.run_id == run_id,
        OrganizationExecutionReservationModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def _require_reservation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    for_update: bool,
) -> OrganizationExecutionReservationModel:
    reservation = await _get_reservation(
        session,
        organization_id=organization_id,
        run_id=run_id,
        for_update=for_update,
    )
    if reservation is None:
        raise ExecutionBudgetConflict("Agent run has no durable budget reservation.")
    return reservation


async def _get_memory_reservation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
    for_update: bool = False,
) -> OrganizationExecutionReservationModel | None:
    owner_column = getattr(
        OrganizationExecutionReservationModel,
        _memory_job_id_attribute(kind),
    )
    query = select(OrganizationExecutionReservationModel).where(
        OrganizationExecutionReservationModel.organization_id == organization_id,
        owner_column == job_id,
        OrganizationExecutionReservationModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def _require_memory_reservation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    job_id: UUID,
    kind: _MemoryExecutionKind,
    for_update: bool,
) -> OrganizationExecutionReservationModel:
    reservation = await _get_memory_reservation(
        session,
        organization_id=organization_id,
        job_id=job_id,
        kind=kind,
        for_update=for_update,
    )
    if reservation is None:
        raise ExecutionBudgetConflict(
            f"{_memory_execution_label(kind)} has no durable budget reservation."
        )
    return reservation


async def _load_active_reservations(
    session: AsyncSession,
    *,
    organization_id: UUID,
    for_update: bool,
) -> list[OrganizationExecutionReservationModel]:
    query = select(OrganizationExecutionReservationModel).where(
        OrganizationExecutionReservationModel.organization_id == organization_id,
        OrganizationExecutionReservationModel.active.is_(True),
        OrganizationExecutionReservationModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    return list((await session.execute(query)).scalars().all())


def _measure_active_capacity(
    reservations: list[OrganizationExecutionReservationModel],
) -> _ActiveCapacity:
    now = _now()
    tokens = 0
    milliseconds = 0
    cost_microunits = 0
    for reservation in reservations:
        elapsed = reservation.active_milliseconds
        if reservation.active_since is not None:
            elapsed += _elapsed_milliseconds(reservation.active_since, now)
        tokens += max(0, reservation.token_limit - reservation.used_tokens)
        milliseconds += max(0, reservation.time_limit_milliseconds - elapsed)
        cost_microunits += max(
            0,
            reservation.cost_limit_microunits - reservation.used_cost_microunits,
        )
    return _ActiveCapacity(
        runs=len(reservations),
        tokens=tokens,
        milliseconds=milliseconds,
        cost_microunits=cost_microunits,
    )


def _require_capacity(
    *,
    policy: OrganizationExecutionBudgetModel | OrganizationExecutionBudgetUpsert,
    active: _ActiveCapacity,
    include_run: bool,
) -> None:
    added_runs = 1 if include_run else 0
    added_tokens = policy.run_token_limit if include_run else 0
    added_time = policy.run_time_limit_milliseconds if include_run else 0
    added_cost = policy.run_cost_limit_microunits if include_run else 0
    boundaries = (
        (
            ExecutionBudgetDimension.CONCURRENCY,
            active.runs + added_runs,
            policy.max_concurrent_runs,
        ),
        (
            ExecutionBudgetDimension.TOKENS,
            active.tokens + added_tokens,
            policy.max_active_tokens,
        ),
        (
            ExecutionBudgetDimension.ACTIVE_TIME,
            active.milliseconds + added_time,
            policy.max_active_milliseconds,
        ),
        (
            ExecutionBudgetDimension.COST,
            active.cost_microunits + added_cost,
            policy.max_active_cost_microunits,
        ),
    )
    for dimension, required, available in boundaries:
        if required > available:
            raise ExecutionBudgetUnavailable(dimension)


def _require_capacity_for_pinned_reservation(
    *,
    policy: OrganizationExecutionBudgetModel,
    active: _ActiveCapacity,
    reservation: OrganizationExecutionReservationModel,
) -> None:
    remaining_tokens = max(0, reservation.token_limit - reservation.used_tokens)
    remaining_time = max(
        0,
        reservation.time_limit_milliseconds - reservation.active_milliseconds,
    )
    remaining_cost = max(
        0,
        reservation.cost_limit_microunits - reservation.used_cost_microunits,
    )
    boundaries = (
        (
            ExecutionBudgetDimension.CONCURRENCY,
            active.runs + 1,
            policy.max_concurrent_runs,
        ),
        (
            ExecutionBudgetDimension.TOKENS,
            active.tokens + remaining_tokens,
            policy.max_active_tokens,
        ),
        (
            ExecutionBudgetDimension.ACTIVE_TIME,
            active.milliseconds + remaining_time,
            policy.max_active_milliseconds,
        ),
        (
            ExecutionBudgetDimension.COST,
            active.cost_microunits + remaining_cost,
            policy.max_active_cost_microunits,
        ),
    )
    for dimension, required, available in boundaries:
        if required > available:
            raise ExecutionBudgetUnavailable(dimension)


def _exceeded_dimension(
    reservation: OrganizationExecutionReservationModel,
) -> ExecutionBudgetDimension | None:
    boundaries = (
        (
            ExecutionBudgetDimension.TOKENS,
            reservation.used_tokens,
            reservation.token_limit,
        ),
        (
            ExecutionBudgetDimension.ACTIVE_TIME,
            reservation.active_milliseconds,
            reservation.time_limit_milliseconds,
        ),
        (
            ExecutionBudgetDimension.COST,
            reservation.used_cost_microunits,
            reservation.cost_limit_microunits,
        ),
    )
    for dimension, used, limit in boundaries:
        if used > limit:
            return dimension
    return None


def _accrue_active_time(
    reservation: OrganizationExecutionReservationModel,
    *,
    now: datetime,
) -> None:
    if reservation.active_since is None:
        return
    elapsed = _elapsed_milliseconds(
        reservation.active_since,
        now,
    )
    if elapsed > 0:
        reservation.active_milliseconds += elapsed
        reservation.active_since = now


def _elapsed_milliseconds(started_at: datetime, now: datetime) -> int:
    return max(0, int((now - started_at).total_seconds() * 1000))


def _cost_microunits(*, tokens: int, rate: int) -> int:
    return (tokens * rate + _MICROUNITS_PER_UNIT - 1) // _MICROUNITS_PER_UNIT


def _budget_values(command: OrganizationExecutionBudgetUpsert) -> dict[str, int]:
    return {
        "max_concurrent_runs": command.max_concurrent_runs,
        "max_active_tokens": command.max_active_tokens,
        "max_active_milliseconds": command.max_active_milliseconds,
        "max_active_cost_microunits": command.max_active_cost_microunits,
        "run_token_limit": command.run_token_limit,
        "run_time_limit_milliseconds": command.run_time_limit_milliseconds,
        "run_cost_limit_microunits": command.run_cost_limit_microunits,
        "cost_microunits_per_million_tokens": (
            command.cost_microunits_per_million_tokens
        ),
    }


def _memory_job_id_attribute(kind: _MemoryExecutionKind) -> str:
    return {
        _MemoryExecutionKind.FORMATION: "memory_formation_job_id",
        _MemoryExecutionKind.RECONCILIATION: "memory_reconciliation_job_id",
    }[kind]


def _memory_execution_label(kind: _MemoryExecutionKind) -> str:
    return {
        _MemoryExecutionKind.FORMATION: "Memory formation",
        _MemoryExecutionKind.RECONCILIATION: "Memory reconciliation",
    }[kind]


def _now() -> datetime:
    return datetime.now(timezone.utc)
