"""Content-free observability listeners for local Memory events."""

from __future__ import annotations

import logging
from enum import Enum

from eylo.events.schema.py_events.memory import (
    MemoryFactsChangedEvent,
    MemoryFormationLifecycleEvent,
    MemoryRecallObservedEvent,
    MemoryReconciliationLifecycleEvent,
    MemoryReindexLifecycleEvent,
)

logger = logging.getLogger(__name__)

MemoryLocalEvent = (
    MemoryFactsChangedEvent
    | MemoryFormationLifecycleEvent
    | MemoryReconciliationLifecycleEvent
    | MemoryReindexLifecycleEvent
    | MemoryRecallObservedEvent
)


async def observe_memory_event(event: MemoryLocalEvent) -> None:
    """Log a bounded identity projection, never Memory fact content."""
    logger.info(
        "Memory local event",
        extra={
            "local_event_name": type(event).__name__,
            "organization_id": str(event.organization_id),
            "memory_provider_config_id": _optional_id(
                event,
                "memory_provider_config_id",
            ),
            "job_id": _optional_id(event, "job_id"),
            "agent_id": _optional_id(event, "agent_id"),
            "transition": _optional_value(event, "transition"),
            "outcome": _optional_value(event, "outcome"),
        },
    )


def _optional_id(event: MemoryLocalEvent, field: str) -> str | None:
    value = getattr(event, field, None)
    return str(value) if value is not None else None


def _optional_value(event: MemoryLocalEvent, field: str) -> str | None:
    value = getattr(event, field, None)
    if isinstance(value, Enum):
        return str(value.value)
    return str(value) if value is not None else None
