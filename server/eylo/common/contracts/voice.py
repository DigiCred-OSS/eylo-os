"""Neutral voice values shared by conversation, transcript and voice runtimes."""

from enum import Enum

VOICE_MESSAGE_META_SESSION_ID = "voice_session_id"
VOICE_MESSAGE_META_SESSION_ROW_ID = "voice_session_row_id"
VOICE_MESSAGE_META_RUNTIME_MODE = "voice_runtime_mode"
VOICE_MESSAGE_META_SPEECH_OUTCOME = "speech_turn_outcome"
VOICE_MESSAGE_META_SOURCE_SEQUENCE = "voice_source_sequence"
VOICE_MESSAGE_META_REDACTION_VERSION = "voice_redaction_version"


class InterruptionType(str, Enum):
    TRANSCRIPT = "transcript"
    VAD = "vad"


class VoiceSpeechOutcome(str, Enum):
    """Eylo-owned terminal result for one assistant speech turn."""

    DRAINED = "drained"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    CANCELLED = "cancelled"


__all__ = [
    "InterruptionType",
    "VOICE_MESSAGE_META_RUNTIME_MODE",
    "VOICE_MESSAGE_META_REDACTION_VERSION",
    "VOICE_MESSAGE_META_SESSION_ID",
    "VOICE_MESSAGE_META_SESSION_ROW_ID",
    "VOICE_MESSAGE_META_SOURCE_SEQUENCE",
    "VOICE_MESSAGE_META_SPEECH_OUTCOME",
    "VoiceSpeechOutcome",
]
