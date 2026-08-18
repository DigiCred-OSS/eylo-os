"""Platform STT event contract.

STT vendors use different names for the same voice activity concepts:
Deepgram emits `SpeechStarted`, Sarvam emits `START_SPEECH`, Flux emits
`StartOfTurn`, and older adapters used `interrupt`. The rest of Eylo should not
need to know those vendor-specific shapes, so STTRealtime normalizes every
vendor response into this small platform contract before consumers see it.
"""

from __future__ import annotations

from typing import Any

from eylo.sockets.stt.schemas import STTEvent


def normalize_stt_event(event: STTEvent) -> dict[str, Any]:
    """Project a canonical STT event onto the websocket voice contract."""
    return event.to_platform_event()
