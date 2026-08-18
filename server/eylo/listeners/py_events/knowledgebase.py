"""PII-free observability listeners for local Knowledgebase events."""

from __future__ import annotations

import logging
from enum import Enum

from eylo.events.schema.py_events.knowledgebase import (
    KnowledgeCorpusImportLifecycleEvent,
    KnowledgeIngestionLifecycleEvent,
    KnowledgeQueryObservedEvent,
    KnowledgeReindexLifecycleEvent,
    KnowledgebaseAccessChangedEvent,
    KnowledgebaseLifecycleEvent,
)

logger = logging.getLogger(__name__)

KnowledgeLocalEvent = (
    KnowledgebaseLifecycleEvent
    | KnowledgebaseAccessChangedEvent
    | KnowledgeIngestionLifecycleEvent
    | KnowledgeCorpusImportLifecycleEvent
    | KnowledgeReindexLifecycleEvent
    | KnowledgeQueryObservedEvent
)


async def observe_knowledge_event(event: KnowledgeLocalEvent) -> None:
    """Log a bounded identity projection, never Knowledge content."""
    logger.info(
        "Knowledgebase local event",
        extra={
            "local_event_name": type(event).__name__,
            "organization_id": str(event.organization_id),
            "knowledgebase_id": _optional_id(event, "knowledgebase_id"),
            "job_id": _optional_id(event, "job_id"),
            "agent_id": _optional_id(event, "agent_id"),
            "transition": _optional_value(event, "transition"),
            "outcome": _optional_value(event, "outcome"),
        },
    )


def _optional_id(event: KnowledgeLocalEvent, field: str) -> str | None:
    value = getattr(event, field, None)
    return str(value) if value is not None else None


def _optional_value(event: KnowledgeLocalEvent, field: str) -> str | None:
    value = getattr(event, field, None)
    if isinstance(value, Enum):
        return str(value.value)
    return str(value) if value is not None else None
