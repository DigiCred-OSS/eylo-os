"""Voice Service Event Schemas

Events emitted by voice services (WebRTC, STT, TTS) to broadcast state changes
to WebSocket clients. These events follow the same pattern as agent lifecycle events.

Architecture:
- Services emit these events when state changes occur
- Listeners (voice_lifecycle.py) catch events and broadcast via WebSocket
- This decouples service logic from WebSocket broadcasting
"""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WebRTCState(str, Enum):
    """WebRTC peer connection states."""

    PEER_CREATED = "peer_created"
    PEER_CONNECTING = "peer_connecting"
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    PEER_FAILED = "peer_failed"
    ICE_GATHERING = "ice_gathering"
    ICE_COMPLETE = "ice_complete"
    TRACK_ADDED = "track_added"
    TRACK_REMOVED = "track_removed"


class STTState(str, Enum):
    """STT (Speech-to-Text) service states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class TTSState(str, Enum):
    """TTS (Text-to-Speech) service states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class VoiceStateEvent(BaseModel):
    """Base event for all voice service state changes."""

    state: WebRTCState | STTState | TTSState = Field(
        ..., description="State identifier (enum converted to string on serialization)"
    )
    message: str = Field(..., description="Human-readable status message")
    session_id: str = Field(..., description="Session ID for WebSocket routing")
    organization_id: UUID = Field(
        ..., description="Organization ID for WebSocket routing"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional event data"
    )


class WebRTCStateEvent(VoiceStateEvent):
    """Event emitted when WebRTC peer connection state changes.

    States:
    - peer_created: Peer connection created
    - peer_connecting: ICE negotiation in progress
    - peer_connected: Peer connection established
    - peer_disconnected: Peer connection lost
    - peer_failed: Peer connection failed
    - ice_gathering: ICE candidate gathering started
    - ice_complete: ICE candidate gathering complete
    - track_added: Media track added to connection
    - track_removed: Media track removed from connection
    """

    pass


class STTStateEvent(VoiceStateEvent):
    """Event emitted when STT (Speech-to-Text) service state changes.

    States:
    - connecting: Connecting to STT service
    - connected: STT service connection established
    - ready: STT service ready to process audio
    - disconnected: STT service disconnected
    - error: STT service error occurred
    """

    vendor: str = Field(..., description="STT vendor name (e.g., 'deepgram')")


class TTSStateEvent(VoiceStateEvent):
    """Event emitted when TTS (Text-to-Speech) service state changes.

    States:
    - connecting: Connecting to TTS service
    - connected: TTS service connection established
    - ready: TTS service ready to synthesize speech
    - disconnected: TTS service disconnected
    - error: TTS service error occurred
    """

    vendor: str = Field(
        ..., description="TTS vendor name (e.g., 'cartesia', 'elevenlabs')"
    )
