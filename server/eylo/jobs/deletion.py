"""Periodic DB-outbox nudge for Absurd-owned deletion jobs."""

from __future__ import annotations

from eylo.pipelines.deletions.durable_execution import spawn_unbound_deletions


async def nudge_unbound_deletions() -> dict[str, int]:
    """Repeat lost producer spawns; never claim or execute erasure work."""
    return {"spawned": await spawn_unbound_deletions()}


__all__ = ["nudge_unbound_deletions"]
