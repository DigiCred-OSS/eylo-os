"""Product-state helpers for work executed by the shared Absurd runtime.

Eylo owns product lifecycle, results, and the exact engine-task binding. Absurd
alone owns claims, retries, heartbeats, checkpoints, and cancellation delivery.
"""

from eylo.absurd_work.binding import (
    cancel_bound_work,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.absurd_work.model import (
    DEFAULT_MAX_ATTEMPTS,
    TERMINAL_STATES,
    AbsurdBoundWorkMixin,
    DurableState,
)
from eylo.absurd_work.service import (
    AbsurdBoundWorkService,
    DurableWorkBindingPending,
    DurableWorkConflict,
    DurableWorkNotFound,
)

__all__ = [
    "AbsurdBoundWorkMixin",
    "AbsurdBoundWorkService",
    "DEFAULT_MAX_ATTEMPTS",
    "TERMINAL_STATES",
    "DurableState",
    "DurableWorkBindingPending",
    "DurableWorkConflict",
    "DurableWorkNotFound",
    "cancel_bound_work",
    "spawn_bound_work",
    "spawn_unbound_work",
]
