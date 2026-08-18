"""Transport-neutral browser voice interaction states."""

from enum import StrEnum


class VoiceInteractionState(StrEnum):
    INITIALIZING = "INITIALIZING"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    INACTIVE = "INACTIVE"
