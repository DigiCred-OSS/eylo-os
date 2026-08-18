"""Importing the modules that register scheduled actions.

The registry is populated by decorators, so a handler only exists once its
module has been imported. This mirrors `register_models()` with an explicit
list, because import-time package scanning is harder to debug than a missing
line.

Called by the worker, so handlers exist before a run is dispatched, and by
anything that validates an action name before storing it.
"""

from __future__ import annotations


def register_scheduled_actions() -> None:
    """Import module-owned actions. Pipeline actions register at composition."""
    import eylo.modules.conversations.scheduled_actions  # noqa: F401
