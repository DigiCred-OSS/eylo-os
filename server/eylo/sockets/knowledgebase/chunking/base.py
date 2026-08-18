"""The chunking contract and its registry."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from eylo.common.contracts.knowledgebase import (
    DEFAULT_KNOWLEDGE_CHUNK_CHARS,
    DEFAULT_KNOWLEDGE_CHUNK_OVERLAP,
    KnowledgeChunkingStrategy,
    chunking_strategy_names,
)

# Defaults for the *parameters*, not for the choice of strategy. An operator
# who names a strategy and no size gets these; an operator who names neither
# gets `paragraph`, which is stated in the knowledgebase's config rather than
# hidden here.
DEFAULT_CHUNK_CHARS = DEFAULT_KNOWLEDGE_CHUNK_CHARS
DEFAULT_OVERLAP = DEFAULT_KNOWLEDGE_CHUNK_OVERLAP

# A chunk smaller than this retrieves badly — it matches on one word and says
# nothing. Strategies pack up to it rather than emitting fragments.
MIN_USEFUL_CHARS = 80

_PARAGRAPH = re.compile(r"\n\s*\n")
# ATX headings only. Setext (`===` underlines) survives extraction as its own
# paragraph anyway, so the packing strategy handles it.
_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)


class UnknownStrategy(Exception):
    """A knowledgebase names a chunking strategy that does not exist."""


class ChunkingStrategy(ABC):
    """Text in, chunks out.

    Deliberately narrower than a document-to-documents transform: metadata,
    scope and identity are the vendor's business, and a strategy that could see
    them would eventually start deciding things that are not chunking.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        """Split `text`. Every chunk must be non-empty and within budget."""
        ...

    def _split_oversized(self, block: str, size: int, overlap: int) -> list[str]:
        """Cut a block too large to be one chunk, with overlap.

        Shared because every strategy needs it for the same reason: a single
        paragraph, section or line can exceed any budget, and a fact spanning
        the cut must stay retrievable from either side.
        """
        chunks: list[str] = []
        start = 0
        while start < len(block):
            end = start + size
            piece = block[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(block):
                break
            start = end - overlap
        return chunks


class ParagraphChunking(ChunkingStrategy):
    """Pack whole paragraphs up to a budget. The default, and right for prose.

    Paragraph breaks are *preferred split points*, not chunk boundaries — the
    distinction that a previous version got wrong, emitting one chunk per
    paragraph so that a heading became a ten-character chunk and an FAQ became
    twenty fragments. Retrieval scores a chunk as a unit, and a query of
    several words can only match a chunk containing all of them.
    """

    def __init__(self, *, size: int = DEFAULT_CHUNK_CHARS, overlap: int = DEFAULT_OVERLAP) -> None:
        self._size = size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "paragraph"

    def chunk(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []

        chunks: list[str] = []
        buffer: list[str] = []
        size = 0

        def flush() -> None:
            nonlocal buffer, size
            if buffer:
                chunks.append("\n\n".join(buffer))
                buffer, size = [], 0

        for paragraph in _PARAGRAPH.split(text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > self._size:
                flush()
                chunks.extend(
                    self._split_oversized(paragraph, self._size, self._overlap)
                )
                continue
            if size and size + len(paragraph) + 2 > self._size:
                flush()
            buffer.append(paragraph)
            size += len(paragraph) + 2

        flush()
        return [chunk for chunk in chunks if chunk]


class FixedChunking(ChunkingStrategy):
    """Cut at a size with overlap, ignoring structure.

    For text that has no structure to respect — call transcripts, logs, OCR
    output. On prose it is strictly worse than paragraph packing, which is why
    it is not the default; on a wall of unbroken text it is the only one that
    behaves, because paragraph packing would emit the whole thing as one
    oversized block and then cut it here anyway.
    """

    def __init__(self, *, size: int = DEFAULT_CHUNK_CHARS, overlap: int = DEFAULT_OVERLAP) -> None:
        self._size = size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "fixed"

    def chunk(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        return [
            chunk
            for chunk in self._split_oversized(text, self._size, self._overlap)
            if chunk
        ]


class MarkdownChunking(ChunkingStrategy):
    """Split on headings, keeping each section whole where it fits.

    Right for documentation, and nearly free: the extraction layer already
    emits Word headings, spreadsheet sheet markers and PDF page markers as
    their own paragraphs, so a converted document arrives with the structure
    this needs.

    **The heading travels with its section.** A chunk that begins "Refunds are
    processed within five business days" without the "## Refund Policy" above
    it has lost the thing that makes it findable.
    """

    def __init__(self, *, size: int = DEFAULT_CHUNK_CHARS, overlap: int = DEFAULT_OVERLAP) -> None:
        self._size = size
        self._overlap = overlap
        self._fallback = ParagraphChunking(size=size, overlap=overlap)

    @property
    def name(self) -> str:
        return "markdown"

    def chunk(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []

        starts = [match.start() for match in _HEADING.finditer(text)]
        if not starts:
            # No headings: this is prose wearing a .md extension, and packing
            # paragraphs is what prose wants.
            return self._fallback.chunk(text)

        if starts[0] > 0:
            starts.insert(0, 0)
        bounds = starts + [len(text)]

        chunks: list[str] = []
        for index in range(len(bounds) - 1):
            section = text[bounds[index] : bounds[index + 1]].strip()
            if not section:
                continue
            if len(section) <= self._size:
                # A heading with no body is merged into the previous chunk
                # rather than emitted — a lone "## Notes" is not a retrievable
                # unit. Merging on *length* instead would swallow real
                # sections that happen to be short, which is the opposite of
                # what splitting on headings is for.
                if (
                    chunks
                    and _is_heading_only(section)
                    and len(chunks[-1]) + len(section) + 2 <= self._size
                ):
                    chunks[-1] = f"{chunks[-1]}\n\n{section}"
                else:
                    chunks.append(section)
                continue

            # A long section is split, and every piece keeps the heading so it
            # stays findable on its own.
            heading, _, body = section.partition("\n")
            pieces = self._split_oversized(body.strip(), self._size, self._overlap)
            chunks.extend(f"{heading}\n\n{piece}" for piece in pieces if piece)

        return [chunk for chunk in chunks if chunk]


def _is_heading_only(section: str) -> bool:
    """True when a section is a heading with nothing under it."""
    _, _, body = section.partition("\n")
    return not body.strip()


_STRATEGIES = {
    KnowledgeChunkingStrategy.PARAGRAPH.value: ParagraphChunking,
    KnowledgeChunkingStrategy.FIXED.value: FixedChunking,
    KnowledgeChunkingStrategy.MARKDOWN.value: MarkdownChunking,
}


def strategy_names() -> tuple[str, ...]:
    return chunking_strategy_names()


def build_chunker(
    name: str | None = None,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> ChunkingStrategy:
    """The strategy a knowledgebase named, or paragraph packing.

    `paragraph` is the default because it is right for prose and prose is most
    documents. It is a *stated* default rather than a hidden one — the
    knowledgebase's config records what it is using, so an operator comparing
    retrieval between two knowledgebases can see the difference.
    """
    chosen = (name or "paragraph").strip().lower()
    strategy = _STRATEGIES.get(chosen)
    if strategy is None:
        raise UnknownStrategy(
            f"Unknown chunking strategy '{name}'. "
            f"Available: {', '.join(strategy_names())}."
        )
    chunk_size = size if size is not None else DEFAULT_CHUNK_CHARS
    chunk_overlap = overlap if overlap is not None else DEFAULT_OVERLAP
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise ValueError("chunk_size must be an integer")
    if isinstance(chunk_overlap, bool) or not isinstance(chunk_overlap, int):
        raise ValueError("chunk_overlap must be an integer")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be non-negative and smaller than chunk_size"
        )
    return strategy(size=chunk_size, overlap=chunk_overlap)
