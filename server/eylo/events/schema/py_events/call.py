"""Call Lifecycle Event Schemas

Events emitted during telephony call lifecycle to broadcast state changes
to WebSocket clients. Follows the same pattern as voice.py (STT/TTS/WebRTC events).

Architecture:
- Telephony services emit these events when call state changes occur
- Listener (call_lifecycle.py) catches events and broadcasts via WebSocket
- This decouples telephony logic from WebSocket broadcasting

Two event categories exist in the platform:
- **Call events (this file)**: py_events for real-time data flow (no DB dependency)
- **Campaign events (future)**: py_events for DB-dependent cross-process coordination
"""

from enum import Enum
from typing import Any, Optional, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CallState(str, Enum):
    """Telephony call states."""

    STARTED = "started"
    RINGING = "ringing"
    CONNECTED = "connected"
    ENDED = "ended"
    TRANSFERRING = "transferring"
    TRANSFERRED = "transferred"


class CallDirection(str, Enum):
    """Call direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStateEvent(BaseModel):
    """Base event for all call lifecycle state changes.

    Carries enough context for listeners to route and broadcast
    without needing to look up additional data.
    """

    state: CallState = Field(..., description="Current call state")
    message: str = Field(..., description="Human-readable status message")
    session_id: str = Field(..., description="Session ID for WebSocket routing")
    organization_id: UUID = Field(
        ..., description="Organization ID for WebSocket routing"
    )
    call_sid: str = Field(..., description="Provider-specific call identifier")
    conversation_id: Optional[UUID] = Field(
        None, description="Eylo conversation ID (set after session init)"
    )
    direction: CallDirection = Field(
        default=CallDirection.INBOUND, description="Call direction"
    )
    provider: str = Field(..., description="Telephony provider name")
    provider_config_id: UUID = Field(
        ...,
        description="Pinned telephony provider config ID",
    )
    provider_config_revision: int = Field(
        ...,
        gt=0,
        description="Pinned telephony provider config revision",
    )
    from_number: Optional[str] = Field(None, description="Caller phone number (E.164)")
    to_number: Optional[str] = Field(None, description="Callee phone number (E.164)")
    agent_id: Optional[UUID] = Field(None, description="Agent ID handling the call")
    agent_revision: Optional[int] = Field(
        None,
        gt=0,
        description="Exact published agent revision handling the call",
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional event data"
    )

    @model_validator(mode="after")
    def exact_agent_ref(self) -> Self:
        if (self.agent_id is None) != (self.agent_revision is None):
            raise ValueError("Call events require a complete exact agent reference.")
        return self


class CallStartedEvent(CallStateEvent):
    """Event emitted when a call is initiated.

    For outbound: emitted when VoiceService.initiate_outbound_call places the call.
    For inbound: emitted when media_stream accepts the WebSocket connection.
    """

    state: CallState = CallState.STARTED


class CallRingingEvent(CallStateEvent):
    """Event emitted when the provider confirms the phone is ringing.

    Primarily relevant for outbound calls. Set via provider status webhooks.
    """

    state: CallState = CallState.RINGING


class CallConnectedEvent(CallStateEvent):
    """Event emitted when the call is connected and media stream is active.

    Emitted from media_stream.py when the first media packet arrives
    or when the call session is fully initialized.
    """

    state: CallState = CallState.CONNECTED


class CallEndedEvent(CallStateEvent):
    """Event emitted when a call terminates.

    Includes the ended_reason for campaign analytics, retry logic,
    and agent performance tracking.
    """

    state: CallState = CallState.ENDED
    ended_reason: str = Field(
        ..., description="CallEndedReason value explaining why the call ended"
    )
    duration_seconds: Optional[float] = Field(
        None, description="Call duration in seconds (if available)"
    )
    terminal_status: Optional[str] = Field(
        None,
        description="Terminal CallStatus value (completed, busy, no-answer, failed, canceled)",
    )


class CallTransferringEvent(CallStateEvent):
    """Event emitted when a call transfer is initiated via transfer_call tool."""

    state: CallState = CallState.TRANSFERRING
    transfer_to: str = Field(..., description="Target phone number for transfer")


class CallTransferredEvent(CallStateEvent):
    """Event emitted when a call transfer completes successfully."""

    state: CallState = CallState.TRANSFERRED
    transfer_to: str = Field(
        ..., description="Target phone number that was transferred to"
    )
