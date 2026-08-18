"""Structural contracts for in-memory interface session state."""

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class WebSocketSessionStatePort(Protocol):
    """Fields session composition consumes from a WebSocket runtime."""

    organization_id: UUID
    session_id: str
    user_session_id: UUID | None
    contact_id: UUID | None
    agent_id: UUID | None
    voice_session_id: UUID | None
    is_voice_mode: bool


@runtime_checkable
class WebRTCSessionStatePort(Protocol):
    """Fields session composition retains from a WebRTC runtime."""

    organization_id: UUID
    session_id: str
    session_state: WebSocketSessionStatePort


@runtime_checkable
class TelephonySessionStatePort(Protocol):
    """Read-only fields session composition consumes from a live call."""

    agent_id: UUID | None
    user_session_id: UUID | None
    voice_session_id: UUID | None
