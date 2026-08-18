"""Persisted cursor contract for long-conversation context compaction."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
)

CONTEXT_COMPACTION_META_KEY = "context_compaction"


class ContextCompactionMeta(BaseModel):
    """Exact persisted boundary represented by one cumulative summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    through_message_id: UUID
    through_created_at: datetime
    source_message_count: int = Field(gt=0)
    previous_summary_id: UUID | None = None


class ContextCompaction(BaseModel):
    """Validated latest summary and the message position it replaces."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    summary: MessageInDb
    boundary: MessageInDb
    meta: ContextCompactionMeta


def ordered_messages(messages: list[MessageInDb]) -> list[MessageInDb]:
    """Return stable persisted message order."""
    return sorted(messages, key=_position)


def latest_summary_message(messages: list[MessageInDb]) -> MessageInDb | None:
    """Return the latest persisted SYSTEM/SUMMARY message."""
    return next(
        (
            message
            for message in reversed(ordered_messages(messages))
            if _is_summary(message)
        ),
        None,
    )


def latest_context_compaction(
    messages: list[MessageInDb],
) -> ContextCompaction | None:
    """Validate the newest summary cursor; invalid metadata fails open."""
    summary = latest_summary_message(messages)
    if summary is None or summary.meta is None:
        return None
    try:
        meta = ContextCompactionMeta.model_validate(
            summary.meta.get(CONTEXT_COMPACTION_META_KEY)
        )
    except Exception:
        return None

    by_id = {message.id: message for message in messages}
    boundary = by_id.get(meta.through_message_id)
    if (
        boundary is None
        or boundary.kind is MessageKind.SYSTEM
        or boundary.created_at != meta.through_created_at
        or _position(boundary) >= _position(summary)
    ):
        return None
    return ContextCompaction(summary=summary, boundary=boundary, meta=meta)


def uncompacted_messages(messages: list[MessageInDb]) -> list[MessageInDb]:
    """Return non-SYSTEM messages not replaced by the latest valid summary."""
    ordered = ordered_messages(messages)
    compaction = latest_context_compaction(ordered)
    if compaction is None:
        return [message for message in ordered if message.kind is not MessageKind.SYSTEM]
    boundary = _position(compaction.boundary)
    return [
        message
        for message in ordered
        if message.kind is not MessageKind.SYSTEM and _position(message) > boundary
    ]


def context_messages(messages: list[MessageInDb]) -> list[MessageInDb]:
    """Return the summary plus uncompacted messages used for token accounting."""
    compaction = latest_context_compaction(messages)
    current = uncompacted_messages(messages)
    if compaction is None:
        return current
    return [compaction.summary, *current]


def compaction_meta(
    *,
    through: MessageInDb,
    source_message_count: int,
    previous_summary_id: UUID | None,
) -> dict:
    """Build JSON-safe cursor metadata for a newly persisted summary."""
    return ContextCompactionMeta(
        through_message_id=through.id,
        through_created_at=through.created_at,
        source_message_count=source_message_count,
        previous_summary_id=previous_summary_id,
    ).model_dump(mode="json")


def _is_summary(message: MessageInDb) -> bool:
    return (
        message.kind is MessageKind.SYSTEM
        and message.content_kind is MessageContentKind.SUMMARY
    )


def _position(message: MessageInDb) -> tuple[datetime, str]:
    return message.created_at, str(message.id)


__all__ = [
    "CONTEXT_COMPACTION_META_KEY",
    "ContextCompaction",
    "ContextCompactionMeta",
    "compaction_meta",
    "context_messages",
    "latest_context_compaction",
    "latest_summary_message",
    "ordered_messages",
    "uncompacted_messages",
]
