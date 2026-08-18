"""Buffer streamed LLM text into vendor-safe TTS chunks.

LLM token streams are optimized for display, not speech synthesis. A token can
be whitespace, punctuation, or half of a word; several TTS vendors reject those
as standalone transcript messages. This module keeps that concern local to the
TTS pipeline by accumulating token deltas until there is speakable text and a
reasonable phrase boundary.
"""

from __future__ import annotations

import re

_STRONG_BOUNDARIES = frozenset(".!?।؟。")
_SOFT_BOUNDARIES = frozenset(",;:，、؛،")
_SOFT_BOUNDARY_MIN_CHARS = 24
_FALLBACK_BOUNDARY_MIN_CHARS = 80
_MAX_CHUNK_CHARS = 180
_SSML_TAG_NAMES = (
    "speak",
    "break",
    "prosody",
    "emphasis",
    "phoneme",
    "sub",
    "say-as",
    "p",
    "s",
    "voice",
    "audio",
)
_WHITESPACE_RE = re.compile(r"\s+")
_SSML_TAG_RE = re.compile(
    rf"</?\s*(?:{'|'.join(_SSML_TAG_NAMES)})\b[^>]*>",
    re.IGNORECASE,
)
_PARTIAL_SSML_TAG_RE = re.compile(
    rf"<\s*/?\s*(?:{'|'.join(_SSML_TAG_NAMES)})\b[^>]*$",
    re.IGNORECASE,
)


def has_speakable_text(text: str) -> bool:
    """Return True when *text* contains at least one language/number character."""
    return any(char.isalnum() for char in text)


def normalize_tts_text(text: str) -> str:
    """Normalize whitespace and remove TTS control markup unsupported by vendors."""
    text = _SSML_TAG_RE.sub(" ", text)
    text = _PARTIAL_SSML_TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


class SpeakableTextBuffer:
    """Accumulate streamed text until it is safe and useful to send to TTS."""

    def __init__(self) -> None:
        self._buffer = ""

    def reset(self) -> None:
        self._buffer = ""

    def add(self, text: str) -> list[str]:
        """Add a token delta and return complete chunks ready for TTS."""
        if not text:
            return []

        self._buffer += text
        chunks: list[str] = []

        while True:
            chunk = self._next_complete_chunk()
            if chunk is None:
                break
            chunks.append(chunk)

        return chunks

    def flush(self) -> list[str]:
        """Return any remaining speakable text and clear punctuation-only leftovers."""
        chunk = normalize_tts_text(self._buffer)
        self.reset()
        if not chunk or not has_speakable_text(chunk):
            return []
        return [chunk]

    def _next_complete_chunk(self) -> str | None:
        if not has_speakable_text(self._buffer):
            return None

        boundary_index = self._find_boundary_index()
        if boundary_index is None:
            return None

        raw_chunk = self._buffer[: boundary_index + 1]
        self._buffer = self._buffer[boundary_index + 1 :]

        chunk = normalize_tts_text(raw_chunk)
        if not chunk or not has_speakable_text(chunk):
            return None
        return chunk

    def _find_boundary_index(self) -> int | None:
        stripped = self._buffer.rstrip()
        if not stripped:
            return None

        last_char = stripped[-1]
        boundary_index = len(stripped) - 1

        if last_char in _STRONG_BOUNDARIES:
            return boundary_index

        if (
            last_char in _SOFT_BOUNDARIES
            and len(normalize_tts_text(stripped)) >= _SOFT_BOUNDARY_MIN_CHARS
        ):
            return boundary_index

        if len(stripped) < _FALLBACK_BOUNDARY_MIN_CHARS:
            return None

        whitespace_index = stripped.rfind(" ", 0, min(len(stripped), _MAX_CHUNK_CHARS))
        if whitespace_index > 0:
            return whitespace_index

        if len(stripped) >= _MAX_CHUNK_CHARS:
            return _MAX_CHUNK_CHARS - 1

        return None
