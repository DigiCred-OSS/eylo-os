"""Tenant-scoped operational facts for durable event delivery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.models import server_now
from eylo.events.durable.domain import EventDeliveryState
from eylo.events.durable.models import EventDeliveryModel, EventOutboxModel
from eylo.events.durable.registry import EventConsumerKey


@dataclass(frozen=True, slots=True, order=True)
class UnsupportedConsumerHealth:
    """One outstanding delivery identity absent from the process manifest."""

    consumer_name: str
    event_type: str
    event_version: int
    delivery_count: int


@dataclass(frozen=True, slots=True)
class EventDeliveryHealth:
    """Payload-free organization delivery snapshot at one database instant."""

    observed_at: datetime
    total_count: int
    pending_count: int
    running_count: int
    succeeded_count: int
    dead_letter_count: int
    oldest_pending_age_seconds: int | None
    registered_consumers: tuple[EventConsumerKey, ...]
    unsupported_consumers: tuple[UnsupportedConsumerHealth, ...]

    @property
    def unsupported_delivery_count(self) -> int:
        return sum(item.delivery_count for item in self.unsupported_consumers)


async def query_event_delivery_health(
    session: AsyncSession,
    *,
    organization_id: UUID,
    registered_consumers: Sequence[EventConsumerKey],
) -> EventDeliveryHealth:
    """Aggregate delivery state without loading event subjects or payloads."""
    observed_at = server_now()
    counts = {state: 0 for state in EventDeliveryState}
    state_rows = await session.execute(
        select(EventDeliveryModel.state, func.count(EventDeliveryModel.id))
        .where(EventDeliveryModel.organization_id == organization_id)
        .group_by(EventDeliveryModel.state)
    )
    for state, count in state_rows:
        counts[state] = int(count)

    oldest_pending_at = await session.scalar(
        select(func.min(EventDeliveryModel.created_at)).where(
            EventDeliveryModel.organization_id == organization_id,
            EventDeliveryModel.state == EventDeliveryState.PENDING,
        )
    )
    oldest_pending_age_seconds = _age_seconds(
        observed_at=observed_at,
        started_at=oldest_pending_at,
    )

    registered = tuple(sorted(set(registered_consumers)))
    registered_set = set(registered)
    outstanding_rows = await session.execute(
        select(
            EventDeliveryModel.consumer_name,
            EventOutboxModel.event_type,
            EventOutboxModel.event_version,
            func.count(EventDeliveryModel.id),
        )
        .join(
            EventOutboxModel,
            and_(
                EventOutboxModel.id == EventDeliveryModel.event_id,
                EventOutboxModel.organization_id == EventDeliveryModel.organization_id,
            ),
        )
        .where(
            EventDeliveryModel.organization_id == organization_id,
            EventDeliveryModel.state != EventDeliveryState.SUCCEEDED,
        )
        .group_by(
            EventDeliveryModel.consumer_name,
            EventOutboxModel.event_type,
            EventOutboxModel.event_version,
        )
    )
    unsupported = tuple(
        sorted(
            UnsupportedConsumerHealth(
                consumer_name=consumer_name,
                event_type=event_type,
                event_version=event_version,
                delivery_count=int(delivery_count),
            )
            for consumer_name, event_type, event_version, delivery_count in (
                outstanding_rows
            )
            if EventConsumerKey(
                consumer_name=consumer_name,
                event_type=event_type,
                event_version=event_version,
            )
            not in registered_set
        )
    )

    return EventDeliveryHealth(
        observed_at=observed_at,
        total_count=sum(counts.values()),
        pending_count=counts[EventDeliveryState.PENDING],
        running_count=counts[EventDeliveryState.RUNNING],
        succeeded_count=counts[EventDeliveryState.SUCCEEDED],
        dead_letter_count=counts[EventDeliveryState.DEAD_LETTER],
        oldest_pending_age_seconds=oldest_pending_age_seconds,
        registered_consumers=registered,
        unsupported_consumers=unsupported,
    )


def _age_seconds(*, observed_at: datetime, started_at: datetime | None) -> int | None:
    if started_at is None:
        return None
    return max(0, int((observed_at - started_at).total_seconds()))


__all__ = [
    "EventDeliveryHealth",
    "UnsupportedConsumerHealth",
    "query_event_delivery_health",
]
