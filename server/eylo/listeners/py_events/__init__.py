"""Explicit setup and health surface for local Pyventus listeners."""

from eylo.listeners.py_events.manifest import (
    ListenerManifestHealth,
    ListenerProcessRole,
    listener_manifest_health,
    setup_listener_manifest,
)


def setup_listeners(
    *,
    process_role: ListenerProcessRole,
) -> ListenerManifestHealth:
    """Register and validate every listener applicable to this process role."""
    return setup_listener_manifest(process_role=process_role)


__all__ = [
    "ListenerManifestHealth",
    "ListenerProcessRole",
    "listener_manifest_health",
    "setup_listeners",
]
