"""Platform-normalized realtime events.

Every vendor adapter translates its protocol into these types.
The pipelines.voice.realtime.RealtimeManager only sees these — never
vendor-specific objects.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.conversation import REALTIME_MESSAGE_SOURCE

# Sentinel used in message meta to skip the agent loop for realtime-persisted messages.
# Referenced in: manager.py (_persist_turn) and listeners/py_events/messages.py
REALTIME_SOURCE = REALTIME_MESSAGE_SOURCE

# Both Gemini Live and OpenAI Realtime output 24kHz PCM.
VENDOR_OUTPUT_SAMPLE_RATE = 24000


class RealtimeEventType(enum.Enum):
    AUDIO_DATA = "audio_data"
    USER_SPEECH_STARTED = "user_speech_started"
    INPUT_TRANSCRIPT = "input_transcript"
    OUTPUT_TRANSCRIPT = "output_transcript"
    TOOL_CALL = "tool_call"
    INTERRUPTION = "interruption"
    TURN_COMPLETE = "turn_complete"
    SESSION_STARTED = "session_started"
    GO_AWAY = "go_away"
    ERROR = "error"


class RealtimeEvent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: RealtimeEventType


class AudioDataEvent(RealtimeEvent):
    """Audio chunk from vendor speech output. Both vendors output PCM 24kHz 16-bit mono."""

    type: RealtimeEventType = RealtimeEventType.AUDIO_DATA
    audio: bytes = b""
    sample_rate: int = VENDOR_OUTPUT_SAMPLE_RATE


class UserSpeechStartedEvent(RealtimeEvent):
    """The provider detected user speech; this is not always an interruption."""

    type: RealtimeEventType = RealtimeEventType.USER_SPEECH_STARTED


class InputTranscriptEvent(RealtimeEvent):
    """User speech transcription from the vendor."""

    type: RealtimeEventType = RealtimeEventType.INPUT_TRANSCRIPT
    text: str = ""
    is_final: bool = False


class OutputTranscriptEvent(RealtimeEvent):
    """Model speech transcription from the vendor."""

    type: RealtimeEventType = RealtimeEventType.OUTPUT_TRANSCRIPT
    text: str = ""
    is_final: bool = False


class ToolCallEvent(RealtimeEvent):
    """Vendor requests tool execution."""

    type: RealtimeEventType = RealtimeEventType.TOOL_CALL
    tool_call_id: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)


class InterruptionEvent(RealtimeEvent):
    """User interrupted model speech (VAD-detected)."""

    type: RealtimeEventType = RealtimeEventType.INTERRUPTION


class TurnCompleteEvent(RealtimeEvent):
    """Model finished a full response turn."""

    type: RealtimeEventType = RealtimeEventType.TURN_COMPLETE


class SessionStartedEvent(RealtimeEvent):
    """Vendor session is ready to receive audio."""

    type: RealtimeEventType = RealtimeEventType.SESSION_STARTED
    session_id: str = ""


class GoAwayEvent(RealtimeEvent):
    """Vendor signals imminent disconnection — reconnect now."""

    type: RealtimeEventType = RealtimeEventType.GO_AWAY
    time_left_ms: int = 0


class ErrorEvent(RealtimeEvent):
    """Vendor-side error."""

    type: RealtimeEventType = RealtimeEventType.ERROR
    message: str = ""
    code: str = ""
    is_recoverable: bool = True
