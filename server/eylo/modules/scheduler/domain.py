"""Scheduler definition errors and exact-reference invariants."""

from __future__ import annotations

from eylo.common.revisions import DefinitionRevisionError


class ScheduleDefinitionError(DefinitionRevisionError):
    """Base error for immutable schedule definition commands."""


class ScheduleConflictError(ScheduleDefinitionError):
    """A stable schedule key or immutable definition command conflicts."""


class ScheduleNotFound(ScheduleDefinitionError):
    """No schedule or exact schedule revision is reachable in caller scope."""


__all__ = ["ScheduleConflictError", "ScheduleDefinitionError", "ScheduleNotFound"]
