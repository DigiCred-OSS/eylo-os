"""Schemas for Plivo Audio Streams WebSocket messages.

Based on production implementations from bolna-ai.
"""

from typing import Optional

from pydantic import BaseModel


class StartMessageData(BaseModel):
    """Data structure for the start message."""

    streamId: str
    callId: str
    from_: Optional[str] = None
    to: Optional[str] = None

    class Config:
        # Allow field aliases
        populate_by_name = True
        extra = "allow"


class StartMessage(BaseModel):
    """Schema for the start message."""

    event: str
    start: StartMessageData


class MediaMessageData(BaseModel):
    """Data structure for the media message."""

    payload: str  # base64-encoded μ-law audio
    timestamp: Optional[str] = None


class MediaMessage(BaseModel):
    """Schema for the media message."""

    event: str
    media: MediaMessageData


class StopMessage(BaseModel):
    """Schema for the stop message."""

    event: str


class CheckpointMessage(BaseModel):
    """Schema for the checkpoint message (Plivo's equivalent of Twilio's mark)."""

    event: str
    name: str


# Outbound messages (sent to Plivo)
class OutboundMediaMessageData(BaseModel):
    """Data for outbound media."""

    payload: str  # base64-encoded audio
    sampleRate: str  # "8000"
    contentType: str  # "audio/x-mulaw" or "wav"


class OutboundMediaMessage(BaseModel):
    """Schema for outbound media messages sent to Plivo."""

    event: str  # "playAudio"
    media: OutboundMediaMessageData


class OutboundCheckpointMessage(BaseModel):
    """Schema for outbound checkpoint messages."""

    event: str  # "checkpoint"
    streamId: str
    name: str


class ClearAudioMessage(BaseModel):
    """Schema for clearAudio message (interruption)."""

    event: str  # "clearAudio"
    streamId: str
