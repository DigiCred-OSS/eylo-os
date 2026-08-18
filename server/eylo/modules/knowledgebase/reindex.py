"""Knowledgebase vector-space transition state."""

from enum import StrEnum


class KnowledgeReindexState(StrEnum):
    """Operator-visible state of one pgvector space transition."""

    ACTIVE = "active"
    REQUIRED = "reindex_required"
    REINDEXING = "reindexing"
    FAILED = "failed"
