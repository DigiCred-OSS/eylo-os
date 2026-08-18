"""Vendor-neutral scheduling contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MisfirePolicy(StrEnum):
    """What to do when several occurrences came due while nothing was running."""

    COALESCE = "coalesce"
    FIRE_ALL = "fire_all"


class Recurrence(BaseModel):
    """When a schedule fires, and in whose clock."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str | None = None
    timezone: str
    starts_at: datetime
    ends_at: datetime | None = None


class DueResolution(BaseModel):
    """What a schedule owes right now, and when it is next owed."""

    model_config = ConfigDict(extra="forbid")

    fire_at: list[datetime] = Field(default_factory=list)
    skipped: int = 0
    next_at: datetime | None = None

    @property
    def is_finished(self) -> bool:
        return self.next_at is None


class SchedulerCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    native_recurrence: bool = False
    push_delivery: bool = False
    updatable: bool = True
    max_schedules: int | None = None


class SchedulerError(Exception):
    """A scheduling operation failed."""

    def __init__(
        self, message: str, *, vendor: str | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.retryable = retryable


class InvalidRecurrence(SchedulerError):
    """The rule, timezone or bounds cannot express a usable schedule."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class ScheduleSpec(BaseModel):
    """A schedule as a vendor receives it."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Stable id, unique per organization.")
    recurrence: Recurrence
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE
    enabled: bool = True
