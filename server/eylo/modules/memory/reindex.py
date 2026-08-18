"""Memory vector-space transition state."""

from enum import StrEnum


class MemoryReindexState(StrEnum):
    """Operator-visible state of one Memory embedding transition."""

    ACTIVE = "active"
    REQUIRED = "reindex_required"
    REINDEXING = "reindexing"
    FAILED = "failed"
