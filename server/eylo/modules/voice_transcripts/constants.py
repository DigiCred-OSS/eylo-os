"""Constants and enums for voice transcript persistence."""

from enum import Enum

from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_REDACTION_VERSION as VOICE_MESSAGE_META_REDACTION_VERSION,
)
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_RUNTIME_MODE as VOICE_MESSAGE_META_RUNTIME_MODE,
)
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_SESSION_ID as VOICE_MESSAGE_META_SESSION_ID,
)
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_SESSION_ROW_ID as VOICE_MESSAGE_META_SESSION_ROW_ID,
)
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_SOURCE_SEQUENCE as VOICE_MESSAGE_META_SOURCE_SEQUENCE,
)
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_SPEECH_OUTCOME as VOICE_MESSAGE_META_SPEECH_OUTCOME,
)
from eylo.common.contracts.voice import (
    VoiceSpeechOutcome as VoiceSpeechOutcome,
)


class VoiceSessionStatus(str, Enum):
    """Lifecycle states for a durable voice transcript session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceCanonicalState(str, Enum):
    """Outcome of destructive post-call canonical history processing."""

    NOT_RUN = "not_run"
    CLEAN = "clean"
    REDACTED = "redacted"
    FAILED = "failed"
    NO_STORAGE = "no_storage"


VOICE_CANONICAL_REDACTION_VERSION = 1


class VoiceRuntimeMode(str, Enum):
    """Supported voice runtime modes."""

    BROWSER_DECOMPOSED = "browser_decomposed"
    BROWSER_REALTIME = "browser_realtime"
    TELEPHONY = "telephony"


class VoiceSegmentRole(str, Enum):
    """Speaker or actor represented by a timeline segment."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class VoiceSegmentType(str, Enum):
    """Kinds of timeline entries in a voice transcript."""

    SPEECH = "speech"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    EVENT = "event"
    SILENCE = "silence"


class VoiceSegmentSource(str, Enum):
    """Subsystem that produced a voice transcript segment."""

    STT = "stt"
    TTS = "tts"
    REALTIME = "realtime"
    TELEPHONY = "telephony"
    TOOL = "tool"
    SYSTEM = "system"
    MESSAGE = "message"


class VoiceAudioTrackKind(str, Enum):
    """Audio track associated with a segment."""

    USER = "user"
    ASSISTANT = "assistant"
    COMBINED = "combined"
