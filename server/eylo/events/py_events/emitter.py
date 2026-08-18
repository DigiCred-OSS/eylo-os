"""Ephemeral event emission for the `events` platform."""

import logging
import os
from types import EllipsisType
from typing import TypeAlias, override

from pydantic import BaseModel
from pyventus.events import AsyncIOEventEmitter, EventEmitter
from pyventus.events import EventLinker as _EventLinker

SubscribableEventType: TypeAlias = (
    str | type[Exception] | type[object] | EllipsisType | type[BaseModel]
)

logger = logging.getLogger(__name__)

EPHEMERAL_EVENT_MAX_BYTES = 64 * 1024

class EyloLinker(_EventLinker):
    @override
    @classmethod
    def get_valid_event_name(cls, event):
        if isinstance(event, type) and issubclass(event, BaseModel):
            return event.__name__
        return super().get_valid_event_name(event)


# ============================================================================
# FORK-SAFE EVENT EMITTER
# ============================================================================
# This implementation prevents SIGSEGV crashes in forked worker processes.
#
# THE PROBLEM:
# -----------
# AsyncIOEventEmitter internally uses asyncio event loops, which hold:
# - Thread-local state (event loop per thread)
# - File descriptors for async I/O
# - Pending callbacks and futures
# - Internal locks and queues
#
# When a process forks:
# 1. Memory is copied (copy-on-write)
# 2. Child gets COPY of parent's memory, including event loop references
# 3. But those references point to parent's thread/loop (which doesn't exist)
# 4. Accessing them = illegal memory access = SIGSEGV (signal 11)
#
# THE SOLUTION:
# ------------
# Lazy initialization with PID-based fork detection:
# 1. Don't create emitter at module import time
# 2. Create on first access, store the process PID
# 3. On subsequent access, check if PID changed (fork detected)
# 4. If forked, create NEW emitter for new process
#
# FLOW:
# -----
# Main Process (PID 1000):
#   - Imports module, _ee = None, _ee_pid = None
#   - (No emitter created yet)
#
# Worker 1 (PID 1001) after fork:
#   - First local emit call
#   - _get_event_emitter() checks: _ee_pid (None) != 1001
#   - Creates NEW emitter for PID 1001
#   - Works correctly! ✅
#
# Worker 2 (PID 1002) after fork:
#   - First local emit call
#   - _get_event_emitter() checks: _ee_pid (None) != 1002
#   - Creates NEW emitter for PID 1002
#   - Works correctly! ✅
#
# WHY THIS WORKS:
# --------------
# Each worker process gets its own fresh AsyncIOEventEmitter instance
# created AFTER fork, with event loop properly initialized in that process.
# No shared state, no invalid references, no crashes.
#
# ============================================================================

_ee: EventEmitter | None = None
_ee_pid: int | None = None


def _get_event_emitter() -> EventEmitter:
    """Get or create fork-safe event emitter instance.

    Returns a new emitter if:
    - First time access in this process
    - Process was forked (PID changed)

    This prevents SIGSEGV errors in multiprocess workers.

    Implementation note:
    The PID check is O(1) and happens on every access, but it's a simple
    integer comparison that's negligible compared to event emission overhead.
    """
    global _ee, _ee_pid

    current_pid = os.getpid()

    # Create new emitter if first access or after fork
    if _ee is None or _ee_pid != current_pid:
        logger.info(f"Initializing event emitter for PID {current_pid}")
        _ee = AsyncIOEventEmitter(event_linker=EyloLinker)
        _ee_pid = current_pid

    return _ee


class _EventEmitterProxy:
    """Proxy that always returns fork-safe emitter instance.

    This ensures that every access to `ee` checks for fork and
    returns the correct per-process emitter instance.
    """

    def __getattr__(self, name):
        """Delegate all attribute access to the current process's emitter."""
        return getattr(_get_event_emitter(), name)

    def __call__(self, *args, **kwargs):
        """Delegate calls to the current process's emitter."""
        return _get_event_emitter()(*args, **kwargs)


# Public API: Fork-safe event emitter that auto-detects fork
# This proxy ensures every access gets the correct per-process emitter
_event_emitter = _EventEmitterProxy()


def emit_ephemeral(event: BaseModel) -> bool:
    """Emit one bounded, best-effort in-process hook or UI delta.

    Local event loss is allowed. Serialization or handler-scheduling failures
    are logged without interrupting the canonical product flow.
    """
    event_name = type(event).__name__
    try:
        payload_size = len(event.model_dump_json().encode())
    except Exception as error:  # noqa: BLE001 - presentation cannot block authority
        logger.error(
            "Could not serialize ephemeral event name=%s error_type=%s",
            event_name,
            type(error).__name__,
        )
        return False
    if payload_size > EPHEMERAL_EVENT_MAX_BYTES:
        logger.warning(
            "Dropped oversized ephemeral event %s (%s > %s bytes).",
            event_name,
            payload_size,
            EPHEMERAL_EVENT_MAX_BYTES,
        )
        return False
    try:
        _event_emitter.emit(event)
    except Exception as error:  # noqa: BLE001 - presentation cannot block authority
        logger.error(
            "Could not schedule ephemeral event name=%s error_type=%s",
            event_name,
            type(error).__name__,
        )
        return False
    return True
