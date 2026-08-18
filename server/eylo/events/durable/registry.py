"""Explicit registry for versioned durable event consumers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.events.durable.domain import (
    DurableEventEnvelope,
    validate_consumer_name,
    validate_event_type,
)

EventConsumer = Callable[
    [AsyncSession, DurableEventEnvelope],
    Awaitable[None],
]


class EventConsumerRegistrationError(Exception):
    """A consumer manifest is invalid or internally ambiguous."""


class EventConsumerNotRegistered(Exception):
    """No exact consumer supports the fact type and schema version."""


class PermanentEventConsumerError(Exception):
    """A consumer rejected a fact that retry cannot make valid."""


@dataclass(frozen=True, slots=True, order=True)
class EventConsumerKey:
    """One exact handler identity in the process manifest."""

    consumer_name: str
    event_type: str
    event_version: int


class EventConsumerRegistry:
    """Resolve required consumers by explicit name, fact type and version."""

    def __init__(self) -> None:
        self._handlers: dict[EventConsumerKey, EventConsumer] = {}

    def register(
        self,
        *,
        consumer_name: str,
        event_type: str,
        event_version: int,
        handler: EventConsumer,
    ) -> EventConsumerKey:
        try:
            name = validate_consumer_name(consumer_name)
            fact_type = validate_event_type(event_type)
        except ValueError as error:
            raise EventConsumerRegistrationError(str(error)) from error
        if not 1 <= event_version <= 32_767:
            raise EventConsumerRegistrationError(
                "event_version must be between 1 and 32767."
            )
        if not callable(handler):
            raise EventConsumerRegistrationError("Consumer handler must be callable.")

        key = EventConsumerKey(
            consumer_name=name,
            event_type=fact_type,
            event_version=event_version,
        )
        if key in self._handlers:
            raise EventConsumerRegistrationError(
                "Durable event consumer registration is duplicated: "
                f"{consumer_name}/{event_type}/v{event_version}."
            )
        self._handlers[key] = handler
        return key

    def resolve(
        self,
        *,
        consumer_name: str,
        envelope: DurableEventEnvelope,
    ) -> EventConsumer:
        key = EventConsumerKey(
            consumer_name=consumer_name,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
        )
        handler = self._handlers.get(key)
        if handler is None:
            raise EventConsumerNotRegistered(
                "No durable consumer is registered for "
                f"{consumer_name}/{envelope.event_type}/v{envelope.event_version}."
            )
        return handler

    def manifest(self) -> tuple[EventConsumerKey, ...]:
        return tuple(sorted(self._handlers))
