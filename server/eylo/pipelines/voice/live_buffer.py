"""Session-local raw voice data that must never become a durable checkpoint."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.pipelines.voice.request_state import VoiceRequestSource

_MAX_BUFFER_BYTES = 16 * 1024 * 1024
_MAX_BUFFER_ITEMS = 10_000


class LiveVoiceItemKind(StrEnum):
    """Raw item kinds retained only for the lifetime of one voice session."""

    USER_TRANSCRIPT = "user_transcript"
    ASSISTANT_TRANSCRIPT = "assistant_transcript"
    SYSTEM_SPEECH = "system_speech"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DTMF = "dtmf"


class LiveVoiceBufferFailure(StrEnum):
    """Why a post-call projection cannot claim a complete source capture."""

    CAPACITY_EXCEEDED = "capacity_exceeded"
    INVALID_PAYLOAD = "invalid_payload"


@dataclass(frozen=True, slots=True)
class LiveVoiceBufferIdentity:
    """Content-free authority for one in-memory call buffer."""

    organization_id: UUID
    conversation_id: UUID
    session_id: str
    voice_session_id: UUID | None
    runtime_mode: VoiceRuntimeMode
    canonical_storage_requested: bool
    contact_id: UUID | None = None
    contact_participant_id: UUID | None = None
    agent_participant_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LiveVoiceDraft:
    """One not-yet-sequenced raw item supplied by a live runtime."""

    kind: LiveVoiceItemKind
    payload: str | dict[str, Any] = field(repr=False)
    turn_index: int | None = None
    participant_id: UUID | None = None
    request_id: UUID | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    is_error: bool | None = None
    speech_outcome: str | None = None
    policy_source: VoiceRequestSource | None = None
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass(frozen=True, slots=True)
class LiveVoiceItem:
    """One raw item with an immutable session-local sequence."""

    sequence: int
    kind: LiveVoiceItemKind
    payload: str | dict[str, Any] = field(repr=False)
    turn_index: int | None = None
    participant_id: UUID | None = None
    request_id: UUID | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    is_error: bool | None = None
    speech_outcome: str | None = None
    policy_source: VoiceRequestSource | None = None
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass(frozen=True, slots=True)
class LiveVoiceBufferSnapshot:
    """Raw post-call input; consumers must redact before any durable write."""

    identity: LiveVoiceBufferIdentity
    items: tuple[LiveVoiceItem, ...] = field(repr=False)
    complete: bool
    failure: LiveVoiceBufferFailure | None
    captured_bytes: int


class LiveVoiceBuffer:
    """Bounded, ordered raw voice state owned by exactly one live call."""

    def __init__(self, identity: LiveVoiceBufferIdentity) -> None:
        self.identity = identity
        self._items: list[LiveVoiceItem] = []
        self._captured_bytes = 0
        self._failure: LiveVoiceBufferFailure | None = None
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def item_count(self) -> int:
        return len(self._items)

    @property
    def captured_bytes(self) -> int:
        return self._captured_bytes

    @property
    def complete(self) -> bool:
        return self._failure is None

    @property
    def closed(self) -> bool:
        return self._closed

    async def append_turn(
        self,
        drafts: list[LiveVoiceDraft],
    ) -> tuple[LiveVoiceItem, ...]:
        """Append one logical batch atomically or mark capture incomplete."""
        if not drafts:
            return ()

        try:
            copied: list[tuple[LiveVoiceDraft, str | dict[str, Any], int]] = []
            for draft in drafts:
                payload = deepcopy(draft.payload)
                copied.append((draft, payload, _payload_bytes(payload)))
        except (RecursionError, TypeError, ValueError):
            async with self._lock:
                if self._closed:
                    raise RuntimeError("Live voice buffer is closed.")
                if self._failure is None:
                    self._failure = LiveVoiceBufferFailure.INVALID_PAYLOAD
            return ()
        async with self._lock:
            if self._closed:
                raise RuntimeError("Live voice buffer is closed.")
            if self._failure is not None:
                return ()
            batch_bytes = sum(size for _, _, size in copied)
            if (
                len(self._items) + len(copied) > _MAX_BUFFER_ITEMS
                or self._captured_bytes + batch_bytes > _MAX_BUFFER_BYTES
            ):
                self._failure = LiveVoiceBufferFailure.CAPACITY_EXCEEDED
                return ()

            start = len(self._items) + 1
            appended = tuple(
                LiveVoiceItem(
                    sequence=start + offset,
                    kind=draft.kind,
                    payload=payload,
                    turn_index=draft.turn_index,
                    participant_id=draft.participant_id,
                    request_id=draft.request_id,
                    tool_call_id=draft.tool_call_id,
                    tool_name=draft.tool_name,
                    is_error=draft.is_error,
                    speech_outcome=draft.speech_outcome,
                    policy_source=draft.policy_source,
                    occurred_at=draft.occurred_at,
                )
                for offset, (draft, payload, _) in enumerate(copied)
            )
            self._items.extend(appended)
            self._captured_bytes += batch_bytes
            return appended

    async def snapshot(self) -> LiveVoiceBufferSnapshot:
        """Copy current raw state without closing the live session."""
        async with self._lock:
            return self._snapshot()

    async def seal(self) -> LiveVoiceBufferSnapshot:
        """Close the buffer and transfer its raw state to post-call processing."""
        async with self._lock:
            self._closed = True
            return self._snapshot()

    async def discard(self) -> None:
        """Close and erase raw memory when no post-call consumer owns it."""
        async with self._lock:
            self._closed = True
            self._items.clear()
            self._captured_bytes = 0

    def mark_speech_outcome(
        self,
        request_id: UUID,
        speech_outcome: str,
    ) -> bool:
        """Attach a terminal playback result to generated speech.

        TTS completion callbacks are synchronous. This mutation has no await and
        therefore cannot interleave with the mutation section of ``append_turn``
        on the same event loop.
        """
        if self._closed:
            return False
        for index in range(len(self._items) - 1, -1, -1):
            item = self._items[index]
            if (
                item.kind
                in {
                    LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
                    LiveVoiceItemKind.SYSTEM_SPEECH,
                }
                and item.request_id == request_id
            ):
                self._items[index] = replace(
                    item,
                    speech_outcome=speech_outcome,
                )
                return True
        return False

    def _snapshot(self) -> LiveVoiceBufferSnapshot:
        return LiveVoiceBufferSnapshot(
            identity=self.identity,
            items=tuple(self._items),
            complete=self.complete,
            failure=self._failure,
            captured_bytes=self._captured_bytes,
        )


def _payload_bytes(payload: str | dict[str, Any]) -> int:
    if isinstance(payload, str):
        return len(payload.encode("utf-8"))
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(encoded.encode("utf-8"))


__all__ = [
    "LiveVoiceBuffer",
    "LiveVoiceBufferFailure",
    "LiveVoiceBufferIdentity",
    "LiveVoiceBufferSnapshot",
    "LiveVoiceDraft",
    "LiveVoiceItem",
    "LiveVoiceItemKind",
]
