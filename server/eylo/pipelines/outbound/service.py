"""Tenant-scoped state transitions for one durable outbound attempt."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.outbound import (
    OUTBOUND_FINAL_STATES,
    OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH,
    OutboundAttemptCancelled,
    OutboundAttemptConflict,
    OutboundAttemptNotFound,
    OutboundAttemptNotSendable,
    OutboundAttemptReconciliationRequired,
    OutboundAttemptSpec,
    OutboundAttemptState,
    require_failure_code,
)
from eylo.pipelines.outbound.models import OutboundAttemptModel


class OutboundAttemptService:
    """Persist and transition effects without owning workflow-engine mechanics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def prepare(self, spec: OutboundAttemptSpec) -> OutboundAttemptModel:
        """Create one stable attempt or return the exact matching existing row."""
        identity = spec.identity
        values = {
            "id": identity.attempt_id,
            "organization_id": identity.organization_id,
            "owner_kind": identity.owner_kind.value,
            "owner_id": identity.owner_id,
            "operation_key": identity.operation_key,
            "provider_operation": spec.provider_operation,
            "transport_kind": spec.transport_kind.value,
            "destination_origin": spec.destination_origin.strip(),
            "request_fingerprint": spec.request_fingerprint,
            "provider_idempotency_key": identity.provider_idempotency_key,
        }
        await self._session.execute(
            insert(OutboundAttemptModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[OutboundAttemptModel.id])
        )
        row = await self.get(
            organization_id=identity.organization_id,
            attempt_id=identity.attempt_id,
        )
        if any(getattr(row, field) != value for field, value in values.items()):
            raise OutboundAttemptConflict(
                "Outbound effect identity conflicts with its committed request."
            )
        return row

    async def get(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        for_update: bool = False,
    ) -> OutboundAttemptModel:
        query = select(OutboundAttemptModel).where(
            OutboundAttemptModel.id == attempt_id,
            OutboundAttemptModel.organization_id == organization_id,
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        if row is None:
            raise OutboundAttemptNotFound("Outbound attempt not found.")
        return row

    async def begin_send(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
    ) -> OutboundAttemptModel:
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if (
            row.cancel_requested_at is not None
            or row.state is OutboundAttemptState.CANCELLED
        ):
            raise OutboundAttemptCancelled("Outbound attempt is cancelled.")
        if row.state is OutboundAttemptState.UNKNOWN:
            raise OutboundAttemptReconciliationRequired(
                "Outbound attempt requires provider reconciliation."
            )
        if row.state not in {
            OutboundAttemptState.PREPARED,
            OutboundAttemptState.RETRYABLE,
        }:
            raise OutboundAttemptNotSendable(
                f"Outbound attempt cannot send from {row.state.value}."
            )

        row.state = OutboundAttemptState.IN_FLIGHT
        row.send_count += 1
        row.started_at = row.started_at or _now()
        row.outcome_at = None
        row.provider_reference = None
        row.status_code = None
        row.failure_code = None
        row.reconciled_at = None
        await self._session.flush()
        return row

    async def record_outcome(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        state: OutboundAttemptState,
        provider_reference: str | None = None,
        status_code: int | None = None,
        failure_code: str | None = None,
    ) -> OutboundAttemptModel:
        if state not in {
            OutboundAttemptState.SUCCEEDED,
            OutboundAttemptState.RETRYABLE,
            OutboundAttemptState.TERMINAL,
            OutboundAttemptState.UNKNOWN,
        }:
            raise ValueError(f"{state.value} is not a send outcome.")
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if row.state in OUTBOUND_FINAL_STATES:
            return row
        if row.state is not OutboundAttemptState.IN_FLIGHT:
            raise OutboundAttemptNotSendable(
                f"Outbound outcome cannot be recorded from {row.state.value}."
            )
        self._apply_outcome(
            row,
            state=state,
            provider_reference=provider_reference,
            status_code=status_code,
            failure_code=failure_code,
        )
        if (
            row.state is OutboundAttemptState.RETRYABLE
            and row.cancel_requested_at is not None
        ):
            row.state = OutboundAttemptState.CANCELLED
        await self._session.flush()
        return row

    async def recover_in_flight_as_unknown(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        failure_code: str,
    ) -> OutboundAttemptModel:
        """Fence an uncheckpointed send replay without performing another send."""
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if row.state is OutboundAttemptState.UNKNOWN:
            return row
        if row.state is not OutboundAttemptState.IN_FLIGHT:
            raise OutboundAttemptNotSendable(
                f"Outbound recovery cannot run from {row.state.value}."
            )
        self._apply_outcome(
            row,
            state=OutboundAttemptState.UNKNOWN,
            provider_reference=None,
            status_code=None,
            failure_code=failure_code,
        )
        await self._session.flush()
        return row

    async def record_preflight_terminal(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        failure_code: str,
    ) -> OutboundAttemptModel:
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if row.state in OUTBOUND_FINAL_STATES:
            return row
        if row.state is not OutboundAttemptState.PREPARED:
            raise OutboundAttemptNotSendable(
                f"Preflight failure cannot be recorded from {row.state.value}."
            )
        row.state = OutboundAttemptState.TERMINAL
        row.outcome_at = _now()
        row.failure_code = require_failure_code(failure_code)
        await self._session.flush()
        return row

    async def request_cancel(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
    ) -> OutboundAttemptModel:
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        row.cancel_requested_at = row.cancel_requested_at or _now()
        if row.state in {
            OutboundAttemptState.PREPARED,
            OutboundAttemptState.RETRYABLE,
        }:
            row.state = OutboundAttemptState.CANCELLED
            row.outcome_at = row.outcome_at or _now()
        await self._session.flush()
        return row

    async def reconcile(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        state: OutboundAttemptState,
        provider_reference: str | None = None,
        status_code: int | None = None,
        failure_code: str | None = None,
    ) -> OutboundAttemptModel:
        if state not in {
            OutboundAttemptState.SUCCEEDED,
            OutboundAttemptState.TERMINAL,
            OutboundAttemptState.UNKNOWN,
        }:
            raise ValueError(
                "Reconciliation must resolve to succeeded, terminal or unknown."
            )
        row = await self.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if row.state is not OutboundAttemptState.UNKNOWN:
            raise OutboundAttemptNotSendable(
                f"Outbound attempt cannot reconcile from {row.state.value}."
            )
        self._apply_outcome(
            row,
            state=state,
            provider_reference=provider_reference,
            status_code=status_code,
            failure_code=failure_code,
        )
        row.reconciled_at = _now()
        await self._session.flush()
        return row

    @staticmethod
    def _apply_outcome(
        row: OutboundAttemptModel,
        *,
        state: OutboundAttemptState,
        provider_reference: str | None,
        status_code: int | None,
        failure_code: str | None,
    ) -> None:
        if state is OutboundAttemptState.SUCCEEDED:
            if failure_code is not None:
                raise ValueError(
                    "Succeeded outbound outcome cannot have a failure code."
                )
        else:
            if failure_code is None:
                raise ValueError(
                    f"{state.value} outbound outcome requires a failure code."
                )
            failure_code = require_failure_code(failure_code)
        if provider_reference is not None:
            provider_reference = provider_reference.strip()
            if (
                not provider_reference
                or len(provider_reference) > OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH
            ):
                raise ValueError("provider_reference must be non-empty and bounded.")
        if status_code is not None and not 100 <= status_code <= 599:
            raise ValueError("status_code must be an HTTP status between 100 and 599.")

        row.state = state
        row.outcome_at = _now()
        row.provider_reference = provider_reference
        row.status_code = status_code
        row.failure_code = failure_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["OutboundAttemptService"]
