"""Memory config catalog."""

from __future__ import annotations

from enum import Enum

__all__ = ["MemoryProviders"]


class MemoryProviders(str, Enum):
    # Our own: pgvector storage with LLM-inferred ADD/UPDATE/DELETE. Uses the
    # organization's explicitly selected embedding and LLM configs, so this
    # capability stores neither dependency's credentials itself.
    PGVECTOR = "pgvector"
