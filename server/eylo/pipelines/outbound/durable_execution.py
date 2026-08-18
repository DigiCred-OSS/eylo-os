"""Absurd-step bridge for one organization-owned external effect."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar
from uuid import UUID

from absurd_sdk import CancelledTask

from eylo.common.database import start_transaction
from eylo.common.outbound import (
    OUTBOUND_FINAL_STATES,
    OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH,
    OutboundAttemptCancelled,
    OutboundAttemptSpec,
    OutboundAttemptState,
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendRetryable,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundSendUnknown,
    require_failure_code,
)
from eylo.pipelines.outbound.models import OutboundAttemptModel
from eylo.pipelines.outbound.service import OutboundAttemptService

T = TypeVar("T")
OutboundSender = Callable[
    [OutboundSendAuthorization],
    Awaitable[OutboundSendOutcome],
]
_SEND_OUTCOME_TYPES = (
    OutboundSendSucceeded,
    OutboundSendRetryable,
    OutboundSendTerminal,
    OutboundSendUnknown,
)
_UNKNOWN_AFTER_INTERRUPTION = "send_interrupted_unconfirmed"
_UNKNOWN_AFTER_EXCEPTION = "send_exception_unconfirmed"
_UNKNOWN_AFTER_REPLAY = "prior_send_unconfirmed"


class DurableStepContext(Protocol):
    """Subset shared by Absurd-backed product workflow contexts."""

    async def step(
        self,
        *,
        key: str,
        version: int,
        operation: Callable[[], Awaitable[T]],
    ) -> T: ...


@dataclass(frozen=True, slots=True)
class OutboundExecutionReceipt:
    """Bounded durable projection safe to checkpoint and show to product code."""

    attempt_id: UUID
    state: OutboundAttemptState
    send_count: int
    cancel_requested: bool
    provider_reference: str | None
    status_code: int | None
    failure_code: str | None

    def __post_init__(self) -> None:
        if not 0 <= self.send_count <= 100:
            raise ValueError("Outbound receipt send count is invalid.")
        if self.provider_reference is not None:
            normalized = self.provider_reference.strip()
            if (
                not normalized
                or normalized != self.provider_reference
                or len(normalized) > OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH
            ):
                raise ValueError("Outbound receipt provider reference is invalid.")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("Outbound receipt status is invalid.")
        if self.failure_code is not None:
            require_failure_code(self.failure_code)
        if not self._has_valid_lifecycle():
            raise ValueError("Outbound receipt lifecycle is invalid.")

    def _has_valid_lifecycle(self) -> bool:
        if self.state is OutboundAttemptState.PREPARED:
            return self.send_count == 0 and self.failure_code is None
        if self.state is OutboundAttemptState.IN_FLIGHT:
            return self.send_count > 0 and self.failure_code is None
        if self.state is OutboundAttemptState.SUCCEEDED:
            return self.send_count > 0 and self.failure_code is None
        if self.state is OutboundAttemptState.RETRYABLE:
            return self.send_count > 0 and self.failure_code is not None
        if self.state is OutboundAttemptState.TERMINAL:
            return self.failure_code is not None
        if self.state is OutboundAttemptState.UNKNOWN:
            return self.send_count > 0 and self.failure_code is not None
        return self.state is OutboundAttemptState.CANCELLED and self.cancel_requested

    @classmethod
    def from_model(cls, row: OutboundAttemptModel) -> OutboundExecutionReceipt:
        return cls(
            attempt_id=UUID(str(row.id)),
            state=row.state,
            send_count=row.send_count,
            cancel_requested=row.cancel_requested_at is not None,
            provider_reference=row.provider_reference,
            status_code=row.status_code,
            failure_code=row.failure_code,
        )

    def as_checkpoint(self) -> dict[str, Any]:
        return {
            "attempt_id": str(self.attempt_id),
            "state": self.state.value,
            "send_count": self.send_count,
            "cancel_requested": self.cancel_requested,
            "provider_reference": self.provider_reference,
            "status_code": self.status_code,
            "failure_code": self.failure_code,
        }

    @classmethod
    def from_checkpoint(cls, value: object) -> OutboundExecutionReceipt:
        if not isinstance(value, dict):
            raise ValueError("Outbound checkpoint must be an object.")
        try:
            attempt_id = UUID(str(value["attempt_id"]))
            state = OutboundAttemptState(str(value["state"]))
            send_count = value["send_count"]
            cancel_requested = value["cancel_requested"]
            provider_reference = value["provider_reference"]
            status_code = value["status_code"]
            failure_code = value["failure_code"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Outbound checkpoint is invalid.") from error
        if isinstance(send_count, bool) or not isinstance(send_count, int):
            raise ValueError("Outbound checkpoint send count is invalid.")
        if send_count < 0 or not isinstance(cancel_requested, bool):
            raise ValueError("Outbound checkpoint lifecycle is invalid.")
        if provider_reference is not None and not isinstance(provider_reference, str):
            raise ValueError("Outbound checkpoint provider reference is invalid.")
        if status_code is not None and (
            isinstance(status_code, bool) or not isinstance(status_code, int)
        ):
            raise ValueError("Outbound checkpoint status is invalid.")
        if failure_code is not None and not isinstance(failure_code, str):
            raise ValueError("Outbound checkpoint failure code is invalid.")
        return cls(
            attempt_id=attempt_id,
            state=state,
            send_count=send_count,
            cancel_requested=cancel_requested,
            provider_reference=provider_reference,
            status_code=status_code,
            failure_code=failure_code,
        )


class OutboundRetryRequested(Exception):
    """Ask Absurd to retry after the provider explicitly allowed another send."""

    def __init__(self, receipt: OutboundExecutionReceipt) -> None:
        if receipt.state is not OutboundAttemptState.RETRYABLE:
            raise ValueError("Outbound retry requires a retryable receipt.")
        self.receipt = receipt
        super().__init__(
            f"Outbound provider requested retry: {receipt.failure_code or 'retryable'}."
        )


async def execute_outbound_attempt(
    *,
    spec: OutboundAttemptSpec,
    context: DurableStepContext,
    sender: OutboundSender,
) -> OutboundExecutionReceipt:
    """Prepare first, then let one Absurd step own send/checkpoint/retry."""
    await _prepare(spec)
    checkpoint = await context.step(
        key=f"outbound:{spec.identity.attempt_id}",
        version=1,
        operation=lambda: _execute_uncheckpointed(spec, sender),
    )
    receipt = OutboundExecutionReceipt.from_checkpoint(checkpoint)
    if receipt.attempt_id != spec.identity.attempt_id:
        raise ValueError("Outbound checkpoint belongs to a different attempt.")
    if receipt.state is OutboundAttemptState.RETRYABLE:
        raise OutboundRetryRequested(receipt)
    return receipt


async def record_outbound_preflight_failure(
    *,
    spec: OutboundAttemptSpec,
    failure_code: str,
) -> OutboundExecutionReceipt:
    """Persist a zero-send terminal failure after product intent is committed."""
    async with start_transaction() as session:
        service = OutboundAttemptService(session)
        row = await service.prepare(spec)
        row = await service.record_preflight_terminal(
            organization_id=spec.identity.organization_id,
            attempt_id=spec.identity.attempt_id,
            failure_code=failure_code,
        )
        return OutboundExecutionReceipt.from_model(row)


async def request_outbound_cancellation(
    *,
    organization_id: UUID,
    attempt_id: UUID,
) -> OutboundExecutionReceipt:
    """Fence future sends; the product owner separately cancels its Absurd task."""
    async with start_transaction() as session:
        row = await OutboundAttemptService(session).request_cancel(
            organization_id=organization_id,
            attempt_id=attempt_id,
        )
        return OutboundExecutionReceipt.from_model(row)


async def _prepare(spec: OutboundAttemptSpec) -> None:
    async with start_transaction() as session:
        await OutboundAttemptService(session).prepare(spec)


async def _execute_uncheckpointed(
    spec: OutboundAttemptSpec,
    sender: OutboundSender,
) -> dict[str, Any]:
    receipt, authorization = await _authorize_or_recover(spec)
    if authorization is None:
        return receipt.as_checkpoint()

    try:
        outcome = await sender(authorization)
        if not isinstance(outcome, _SEND_OUTCOME_TYPES):
            raise TypeError("Outbound sender returned an unsupported outcome.")
        receipt = await _record_send_outcome(spec, outcome)
    except (CancelledTask, asyncio.CancelledError):
        await _recover_unknown_if_in_flight(
            spec,
            failure_code=_UNKNOWN_AFTER_INTERRUPTION,
        )
        raise
    except Exception:
        receipt = await _recover_unknown_if_in_flight(
            spec,
            failure_code=_UNKNOWN_AFTER_EXCEPTION,
        )

    if receipt.state is OutboundAttemptState.RETRYABLE:
        raise OutboundRetryRequested(receipt)
    return receipt.as_checkpoint()


async def _authorize_or_recover(
    spec: OutboundAttemptSpec,
) -> tuple[OutboundExecutionReceipt, OutboundSendAuthorization | None]:
    organization_id = spec.identity.organization_id
    attempt_id = spec.identity.attempt_id
    async with start_transaction() as session:
        service = OutboundAttemptService(session)
        row = await service.get(
            organization_id=organization_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if row.state is OutboundAttemptState.IN_FLIGHT:
            row = await service.recover_in_flight_as_unknown(
                organization_id=organization_id,
                attempt_id=attempt_id,
                failure_code=_UNKNOWN_AFTER_REPLAY,
            )
            return OutboundExecutionReceipt.from_model(row), None
        if (
            row.state in OUTBOUND_FINAL_STATES
            or row.state is OutboundAttemptState.UNKNOWN
        ):
            return OutboundExecutionReceipt.from_model(row), None
        try:
            row = await service.begin_send(
                organization_id=organization_id,
                attempt_id=attempt_id,
            )
        except OutboundAttemptCancelled:
            row = await service.get(
                organization_id=organization_id,
                attempt_id=attempt_id,
            )
            return OutboundExecutionReceipt.from_model(row), None
        return OutboundExecutionReceipt.from_model(row), OutboundSendAuthorization(
            attempt_id=attempt_id,
            provider_idempotency_key=row.provider_idempotency_key,
        )


async def _record_send_outcome(
    spec: OutboundAttemptSpec,
    outcome: OutboundSendOutcome,
) -> OutboundExecutionReceipt:
    async with start_transaction() as session:
        row = await OutboundAttemptService(session).record_outcome(
            organization_id=spec.identity.organization_id,
            attempt_id=spec.identity.attempt_id,
            state=outcome.state,
            provider_reference=outcome.provider_reference,
            status_code=outcome.status_code,
            failure_code=getattr(outcome, "failure_code", None),
        )
        return OutboundExecutionReceipt.from_model(row)


async def _recover_unknown_if_in_flight(
    spec: OutboundAttemptSpec,
    *,
    failure_code: str,
) -> OutboundExecutionReceipt:
    async with start_transaction() as session:
        service = OutboundAttemptService(session)
        row = await service.get(
            organization_id=spec.identity.organization_id,
            attempt_id=spec.identity.attempt_id,
            for_update=True,
        )
        if row.state is OutboundAttemptState.IN_FLIGHT:
            row = await service.recover_in_flight_as_unknown(
                organization_id=spec.identity.organization_id,
                attempt_id=spec.identity.attempt_id,
                failure_code=failure_code,
            )
        return OutboundExecutionReceipt.from_model(row)


__all__ = [
    "DurableStepContext",
    "OutboundExecutionReceipt",
    "OutboundRetryRequested",
    "OutboundSender",
    "execute_outbound_attempt",
    "record_outbound_preflight_failure",
    "request_outbound_cancellation",
]
