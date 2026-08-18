"""SessionContext — unified session model composed at interface boundaries.

Wraps existing session objects (auth, ws, call, webrtc) as optional
attributes and carries the durable voice session id when a voice runtime
has started. Never persisted — assembled per-request or per-connection
and passed as a function argument through the call stack.
"""

from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.session_state import (
    TelephonySessionStatePort,
    WebRTCSessionStatePort,
    WebSocketSessionStatePort,
)
from eylo.modules.auth.schemas import AuthSessionInDb


class SessionChannel(str, enum.Enum):
    """The interface through which this session was initiated."""

    HTTP = "http"
    WEBSOCKET = "websocket"
    TELEPHONY = "telephony"
    WEBRTC = "webrtc"


class SessionContext(BaseModel):
    """Unified session context composed at the interface boundary.

    Wraps existing session objects as optional attributes.
    Never persisted — assembled per-request or per-connection and
    passed as a function argument through the call stack.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- Always present ---
    channel: SessionChannel = Field(
        ..., description="Interface that initiated this session"
    )
    organization_id: UUID = Field(..., description="Organization scope")
    session_id: str = Field(
        ..., description="Interface-local routing session ID; never auth authority."
    )
    user_session_id: Optional[UUID] = Field(
        default=None,
        description="Durable end-user visit/call identity; never an auth session ID.",
    )

    # --- Present after identification ---
    contact_id: Optional[UUID] = Field(default=None, description="Resolved contact ID")
    voice_session_id: Optional[UUID] = Field(
        default=None,
        description="Durable voice_sessions row id for active/recent voice runtime.",
    )
    authorized_agent_id: Optional[UUID] = Field(
        default=None,
        description="Exact Agent granted to a bounded widget session.",
    )
    authorized_agent_revision: Optional[int] = Field(
        default=None,
        gt=0,
        description="Exact published Agent revision granted to the session.",
    )
    authorized_conversation_id: Optional[UUID] = Field(
        default=None,
        description="Only conversation available to a bounded widget session.",
    )

    # --- Composed session objects (populated per channel) ---
    auth: Optional[AuthSessionInDb] = Field(
        default=None,
        description="DB-persisted widget auth session.",
    )
    ws: Optional[WebSocketSessionStatePort] = Field(
        default=None,
        description="In-memory WebSocket connection state.",
    )
    call: Optional[TelephonySessionStatePort] = Field(
        default=None,
        description="In-memory telephony call state. TELEPHONY channel only.",
    )
    webrtc: Optional[WebRTCSessionStatePort] = Field(
        default=None,
        description="In-memory WebRTC peer state. WEBRTC channel only.",
    )

    # --- Computed properties ---

    @property
    def agent_id(self) -> Optional[UUID]:
        """Current agent in conversation, if set.

        Prefers call session (telephony sets agent_id at call start),
        falls back to ws session.
        """
        if self.call is not None and self.call.agent_id is not None:
            return self.call.agent_id
        if self.ws is not None:
            return self.ws.agent_id
        return None

    @property
    def is_telephony(self) -> bool:
        return self.channel == SessionChannel.TELEPHONY

    @property
    def is_webrtc(self) -> bool:
        return self.channel == SessionChannel.WEBRTC

    @property
    def is_browser(self) -> bool:
        return self.channel in (SessionChannel.HTTP, SessionChannel.WEBSOCKET)

    @property
    def is_websocket(self) -> bool:
        """True if the session has a live WebSocket (WS, telephony, or WebRTC)."""
        return self.channel in (
            SessionChannel.WEBSOCKET,
            SessionChannel.TELEPHONY,
            SessionChannel.WEBRTC,
        )

    @property
    def is_voice(self) -> bool:
        """True if the session has an active voice pipeline."""
        if self.is_telephony or self.is_webrtc:
            return True
        if self.ws is not None and self.ws.is_voice_mode:
            return True
        return False

    def allows_agent(self, agent_id: UUID, revision: int | None = None) -> bool:
        """Return whether this session may address the exact Agent reference."""
        if self.authorized_agent_id is None:
            return True
        if str(self.authorized_agent_id) != str(agent_id):
            return False
        return revision is None or self.authorized_agent_revision == revision

    def allows_conversation(self, conversation_id: UUID) -> bool:
        """Return whether this session may address the conversation."""
        return self.authorized_conversation_id is None or str(
            self.authorized_conversation_id
        ) == str(conversation_id)

    def enrich(self, **kwargs) -> SessionContext:
        """Return a new SessionContext with additional attributes set.

        Used for progressive hydration (e.g., adding webrtc to an
        existing WS context).

        Example:
            ctx = ctx.enrich(webrtc=webrtc_session, channel=SessionChannel.WEBRTC)

        """
        return self.model_copy(update=kwargs)
