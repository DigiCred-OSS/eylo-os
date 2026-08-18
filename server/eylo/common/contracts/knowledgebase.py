"""Vendor-neutral knowledgebase contracts."""

from __future__ import annotations

import hashlib
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeScope(StrEnum):
    """Who a document belongs to."""

    ORGANIZATION = "organization"
    AGENT = "agent"
    CONVERSATION = "conversation"


class KnowledgeAccess(StrEnum):
    """What a grant permits. A property of the grant, not of the agent."""

    READ = "read"
    READ_WRITE = "read_write"


class KnowledgeChunkingStrategy(StrEnum):
    """Stable strategy names shared by config validation and chunking adapters."""

    FIXED = "fixed"
    MARKDOWN = "markdown"
    PARAGRAPH = "paragraph"


DEFAULT_KNOWLEDGE_CHUNKING = KnowledgeChunkingStrategy.PARAGRAPH
DEFAULT_KNOWLEDGE_CHUNK_CHARS = 1200
DEFAULT_KNOWLEDGE_CHUNK_OVERLAP = 150
MIN_KNOWLEDGE_CHUNK_CHARS = 80
MAX_KNOWLEDGE_CHUNK_CHARS = 32_000
MAX_KNOWLEDGE_QUERY_CHARS = 8_000
MAX_KNOWLEDGE_SCOPE_FILTERS = 3
MAX_KNOWLEDGE_SOURCE_URI_CHARS = 4_096
MAX_KNOWLEDGE_TITLE_CHARS = 512
MAX_KNOWLEDGE_METADATA_BYTES = 64_000
MAX_KNOWLEDGE_RESULTS = 8


def chunking_strategy_names() -> tuple[str, ...]:
    """Return public strategy names in their existing sorted order."""
    return tuple(strategy.value for strategy in KnowledgeChunkingStrategy)


DOCUMENT_NAMESPACE = uuid.UUID("6f1c3f7a-2d9b-5e64-9c2a-4f0d8b7e1a35")


class KnowledgeDocument(BaseModel):
    """A document going in. The vendor decides how to store it."""

    model_config = ConfigDict(extra="forbid")

    content: str
    scope: KnowledgeScope
    scope_id: str
    title: str | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def identity(self) -> str:
        """What makes this document this document."""
        return derive_identity(
            self.scope,
            self.scope_id,
            source_uri=self.source_uri,
            content=self.content,
        )

    @property
    def document_id(self) -> str:
        """The stable id this document occupies in any vendor."""
        return derive_document_id(self.identity)


def derive_identity(
    scope: KnowledgeScope,
    scope_id: str,
    *,
    source_uri: str | None = None,
    content: str | None = None,
) -> str:
    """Derive one stable identity from scope and source or content."""
    if source_uri:
        tail = source_uri
    elif content is not None:
        tail = hashlib.sha256(content.encode("utf-8")).hexdigest()
    else:
        raise ValueError("A document needs a source_uri or content to have an identity.")
    return f"{scope.value}:{scope_id}:{tail}"


def derive_document_id(identity: str) -> str:
    """The stable id an identity occupies in any vendor."""
    return str(uuid.uuid5(DOCUMENT_NAMESPACE, identity))


class KnowledgeResult(BaseModel):
    """One retrieved document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    content: str
    score: float
    scope: KnowledgeScope
    scope_id: str
    title: str | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgebaseCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    semantic_search: bool = False
    keyword_search: bool = False
    hybrid_search: bool = False
    metadata_filtering: bool = True
    single_document_delete: bool = True


class KnowledgebaseError(Exception):
    """A knowledgebase operation failed."""

    def __init__(
        self,
        message: str,
        *,
        vendor: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.retryable = retryable
