"""Validated vocabulary for unordered durable event facts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

EVENT_PAYLOAD_MAX_BYTES = 65_536
MAX_DELIVERY_ATTEMPTS = 3
_QUALIFIED_NAME_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_QUALIFIED_NAME = re.compile(_QUALIFIED_NAME_PATTERN)


class EventDeliveryState(str, Enum):
    """Persistence state for one explicit event consumer."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class DurableEventEnvelope(BaseModel):
    """One immutable, tenant-owned fact with no ordering promise."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: UUID
    organization_id: UUID
    subject_type: str = Field(
        min_length=1,
        max_length=128,
        pattern=_QUALIFIED_NAME_PATTERN,
    )
    subject_id: UUID
    event_type: str = Field(
        min_length=1,
        max_length=192,
        pattern=_QUALIFIED_NAME_PATTERN,
    )
    event_version: int = Field(ge=1, le=32_767)
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_fact(self) -> DurableEventEnvelope:
        for field_name in ("occurred_at", "recorded_at"):
            value = getattr(self, field_name)
            if value.utcoffset() != timedelta(0):
                raise ValueError(f"{field_name} must be an aware UTC datetime.")
        if self.recorded_at < self.occurred_at:
            raise ValueError("recorded_at cannot precede occurred_at.")
        if self.causation_id == self.event_id:
            raise ValueError("An event cannot cause itself.")

        encoded_payload = json.dumps(
            self.payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded_payload) > EVENT_PAYLOAD_MAX_BYTES:
            raise ValueError(
                f"payload exceeds {EVENT_PAYLOAD_MAX_BYTES} encoded bytes."
            )
        return self


def _validate_qualified_name(value: str, *, field_name: str) -> str:
    if not 1 <= len(value) <= 192 or _QUALIFIED_NAME.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a qualified lowercase name.")
    return value


def validate_consumer_name(value: str) -> str:
    """Validate one stable consumer identity without normalizing it."""
    return _validate_qualified_name(value, field_name="consumer_name")


def validate_event_type(value: str) -> str:
    """Validate one versioned fact type without normalizing it."""
    return _validate_qualified_name(value, field_name="event_type")
