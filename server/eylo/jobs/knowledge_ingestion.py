"""Periodic DB-outbox nudge for knowledge work already owned by Absurd."""

from __future__ import annotations

from eylo.pipelines.knowledgebase.corpus_durable_execution import (
    spawn_unbound_knowledge_corpora,
)
from eylo.pipelines.knowledgebase.durable_execution import (
    spawn_unbound_knowledge_ingestions,
)
from eylo.pipelines.knowledgebase.reindex_durable_execution import (
    spawn_unbound_knowledge_reindexes,
)


async def nudge_unbound_knowledge_work() -> dict[str, int]:
    """Repeat lost producer spawns; never claim or execute product work."""
    return {
        "ingestions_spawned": await spawn_unbound_knowledge_ingestions(),
        "corpora_spawned": await spawn_unbound_knowledge_corpora(),
        "reindexes_spawned": await spawn_unbound_knowledge_reindexes(),
    }


__all__ = ["nudge_unbound_knowledge_work"]
