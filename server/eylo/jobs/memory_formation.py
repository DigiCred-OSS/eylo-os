"""Periodic DB-outbox nudge for Absurd-owned memory formation work."""

from __future__ import annotations

from eylo.pipelines.memory.durable_execution import (
    spawn_unbound_memory_formations,
)
from eylo.pipelines.memory.reconciliation_durable_execution import (
    spawn_unbound_memory_reconciliations,
)
from eylo.pipelines.memory.reindex_durable_execution import (
    spawn_unbound_memory_reindexes,
)


async def nudge_unbound_memory_formations() -> dict[str, int]:
    """Repeat lost producer spawns; never claim or execute memory work."""
    return {"spawned": await spawn_unbound_memory_formations()}


async def nudge_unbound_memory_reindexes() -> dict[str, int]:
    """Repeat lost Memory reindex spawns; never execute product work."""
    return {"spawned": await spawn_unbound_memory_reindexes()}


async def nudge_unbound_memory_reconciliations() -> dict[str, int]:
    """File changed partitions and repeat lost reconciliation spawns."""
    return {"spawned": await spawn_unbound_memory_reconciliations()}


__all__ = [
    "nudge_unbound_memory_formations",
    "nudge_unbound_memory_reconciliations",
    "nudge_unbound_memory_reindexes",
]
