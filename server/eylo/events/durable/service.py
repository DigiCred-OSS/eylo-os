"""Transactional filing and delivery transitions for durable event facts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.events.durable.domain import (
    DurableEventEnvelope,
    EventDeliveryState,
    validate_consumer_name,
)
from eylo.events.durable.models import (
    EventDeliveryModel,
    EventInboxReceiptModel,
    EventOutboxModel,
)
from eylo.events.durable.registry import EventConsumer


class DurableEventConflict(Exception):
    """A stable event or delivery identity conflicts with persisted authority."""


class EventDeliveryNotFound(Exception):
    """The IDs do not resolve to an organization-owned delivery."""


class EventDeliveryBindingPending(Exception):
    """Absurd claimed a task before its product binding became visible."""


@dataclass(frozen=True, slots=True)
class DurableEventFiling:
    """Stable identities produced by one atomic source transaction."""

    event_id: UUID
    delivery_ids: tuple[UUID, ...]
    created: bool


@dataclass(frozen=True, slots=True)
class EventDeliveryAttempt:
    """One product attempt projection loaded after Absurd owns the claim."""

    delivery_id: UUID
    consumer_name: str
    envelope: DurableEventEnvelope
    state: EventDeliveryState
    attempts: int
    should_consume: bool


class DurableEventService:
    """Append facts and their complete explicit consumer set atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def file(
        self,
        *,
        envelope: DurableEventEnvelope,
        consumer_names: Sequence[str],
    ) -> DurableEventFiling:
        consumers = tuple(validate_consumer_name(name) for name in consumer_names)
        if len(consumers) != len(set(consumers)):
            raise ValueError("A durable event consumer list cannot contain duplicates.")
        consumers = tuple(sorted(consumers))

        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": f"durable-event:{envelope.event_id}"},
        )
        existing = await self.session.scalar(
            select(EventOutboxModel)
            .where(EventOutboxModel.id == envelope.event_id)
            .with_for_update()
        )
        if existing is not None:
            return await self._existing_filing(
                existing=existing,
                expected=envelope,
                expected_consumers=consumers,
            )

        self.session.add(
            EventOutboxModel(
                id=envelope.event_id,
                organization_id=envelope.organization_id,
                subject_type=envelope.subject_type,
                subject_id=envelope.subject_id,
                event_type=envelope.event_type,
                event_version=envelope.event_version,
                occurred_at=envelope.occurred_at,
                recorded_at=envelope.recorded_at,
                correlation_id=envelope.correlation_id,
                causation_id=envelope.causation_id,
                payload=envelope.payload,
            )
        )
        await self.session.flush()

        deliveries = [
            EventDeliveryModel(
                id=uuid4(),
                event_id=envelope.event_id,
                organization_id=envelope.organization_id,
                consumer_name=consumer_name,
            )
            for consumer_name in consumers
        ]
        self.session.add_all(deliveries)
        await self.session.flush()
        return DurableEventFiling(
            event_id=envelope.event_id,
            delivery_ids=tuple(delivery.id for delivery in deliveries),
            created=True,
        )

    async def _existing_filing(
        self,
        *,
        existing: EventOutboxModel,
        expected: DurableEventEnvelope,
        expected_consumers: tuple[str, ...],
    ) -> DurableEventFiling:
        persisted = _envelope_from_row(existing)
        if persisted != expected:
            raise DurableEventConflict(
                "Stable event ID is already bound to a different envelope."
            )
        deliveries = list(
            (
                await self.session.scalars(
                    select(EventDeliveryModel)
                    .where(EventDeliveryModel.event_id == existing.id)
                    .order_by(EventDeliveryModel.consumer_name.asc())
                )
            ).all()
        )
        if tuple(row.consumer_name for row in deliveries) != expected_consumers:
            raise DurableEventConflict(
                "Stable event ID is already bound to a different consumer set."
            )
        return DurableEventFiling(
            event_id=existing.id,
            delivery_ids=tuple(row.id for row in deliveries),
            created=False,
        )


class EventDeliveryService:
    """Project delivery audit while Absurd owns execution mechanics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        for_update: bool = False,
    ) -> tuple[EventDeliveryModel, DurableEventEnvelope]:
        query = (
            select(EventDeliveryModel, EventOutboxModel)
            .join(
                EventOutboxModel,
                EventOutboxModel.id == EventDeliveryModel.event_id,
            )
            .where(
                EventDeliveryModel.id == delivery_id,
                EventDeliveryModel.organization_id == organization_id,
                EventOutboxModel.organization_id == organization_id,
            )
        )
        if for_update:
            query = query.with_for_update()
        row = (await self.session.execute(query)).one_or_none()
        if row is None:
            raise EventDeliveryNotFound
        delivery, event = row
        return delivery, _envelope_from_row(event)

    async def bind_task(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        task_id: UUID,
    ) -> bool:
        delivery, _ = await self.get(
            organization_id=organization_id,
            delivery_id=delivery_id,
            for_update=True,
        )
        if delivery.absurd_task_id is not None:
            if delivery.absurd_task_id != task_id:
                raise DurableEventConflict(
                    "Event delivery is already bound to another Absurd task."
                )
            return False
        if delivery.state is not EventDeliveryState.PENDING:
            raise DurableEventConflict(
                f"A {delivery.state.value} delivery cannot bind an Absurd task."
            )
        delivery.absurd_task_id = task_id
        await self.session.flush()
        return True

    async def begin_attempt(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
    ) -> EventDeliveryAttempt:
        delivery, envelope = await self.get(
            organization_id=organization_id,
            delivery_id=delivery_id,
            for_update=True,
        )
        if delivery.state is EventDeliveryState.SUCCEEDED:
            await self._require_receipt(delivery)
            return _attempt(delivery, envelope, should_consume=False)
        if delivery.state is EventDeliveryState.DEAD_LETTER:
            return _attempt(delivery, envelope, should_consume=False)
        if delivery.absurd_task_id is None:
            raise EventDeliveryBindingPending(
                "Event delivery task binding is not visible yet."
            )
        if delivery.state not in {
            EventDeliveryState.PENDING,
            EventDeliveryState.RUNNING,
        }:
            raise DurableEventConflict(
                f"A {delivery.state.value} delivery cannot begin an attempt."
            )
        if delivery.attempts >= delivery.max_attempts:
            delivery.state = EventDeliveryState.DEAD_LETTER
            delivery.last_error = (
                delivery.last_error
                or "Delivery attempt budget was exhausted before completion."
            )
            delivery.finished_at = datetime.now(timezone.utc)
            await self.session.flush()
            return _attempt(delivery, envelope, should_consume=False)

        delivery.state = EventDeliveryState.RUNNING
        delivery.attempts += 1
        delivery.started_at = delivery.started_at or datetime.now(timezone.utc)
        await self.session.flush()
        return _attempt(delivery, envelope, should_consume=True)

    async def consume(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        handler: EventConsumer,
    ) -> bool:
        delivery, envelope = await self.get(
            organization_id=organization_id,
            delivery_id=delivery_id,
            for_update=True,
        )
        receipt = await self.session.scalar(
            select(EventInboxReceiptModel).where(
                EventInboxReceiptModel.delivery_id == delivery.id
            )
        )
        if receipt is not None:
            if delivery.state is not EventDeliveryState.SUCCEEDED:
                raise DurableEventConflict(
                    "Event receipt exists without a succeeded delivery."
                )
            return False
        if delivery.state is EventDeliveryState.SUCCEEDED:
            raise DurableEventConflict(
                "Succeeded event delivery is missing its receipt."
            )
        if delivery.state is not EventDeliveryState.RUNNING:
            raise DurableEventConflict(
                f"A {delivery.state.value} delivery cannot be consumed."
            )

        await handler(self.session, envelope)
        self.session.add(
            EventInboxReceiptModel(
                delivery_id=delivery.id,
                event_id=delivery.event_id,
                organization_id=delivery.organization_id,
                consumer_name=delivery.consumer_name,
            )
        )
        delivery.state = EventDeliveryState.SUCCEEDED
        delivery.last_error = None
        delivery.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def record_failure(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        error_code: str,
        permanent: bool,
    ) -> EventDeliveryState:
        delivery, _ = await self.get(
            organization_id=organization_id,
            delivery_id=delivery_id,
            for_update=True,
        )
        if delivery.state in {
            EventDeliveryState.SUCCEEDED,
            EventDeliveryState.DEAD_LETTER,
        }:
            return delivery.state
        if delivery.state is not EventDeliveryState.RUNNING:
            raise DurableEventConflict(
                f"A {delivery.state.value} delivery cannot record failure."
            )

        if error_code not in {
            "consumer_not_registered",
            "consumer_rejected",
            "delivery_failed",
        }:
            raise DurableEventConflict("Event delivery failure code is invalid.")
        delivery.last_error = error_code
        if permanent or delivery.attempts >= delivery.max_attempts:
            delivery.state = EventDeliveryState.DEAD_LETTER
            delivery.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return delivery.state

    async def _require_receipt(self, delivery: EventDeliveryModel) -> None:
        receipt = await self.session.scalar(
            select(EventInboxReceiptModel.id).where(
                EventInboxReceiptModel.delivery_id == delivery.id
            )
        )
        if receipt is None:
            raise DurableEventConflict(
                "Succeeded event delivery is missing its receipt."
            )


def _envelope_from_row(row: EventOutboxModel) -> DurableEventEnvelope:
    return DurableEventEnvelope(
        event_id=row.id,
        organization_id=row.organization_id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        event_type=row.event_type,
        event_version=row.event_version,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        payload=row.payload,
    )


def _attempt(
    delivery: EventDeliveryModel,
    envelope: DurableEventEnvelope,
    *,
    should_consume: bool,
) -> EventDeliveryAttempt:
    return EventDeliveryAttempt(
        delivery_id=delivery.id,
        consumer_name=delivery.consumer_name,
        envelope=envelope,
        state=delivery.state,
        attempts=delivery.attempts,
        should_consume=should_consume,
    )
