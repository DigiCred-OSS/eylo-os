"""Private WebRTC negotiation aggregate and signaling contracts."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from aiortc import RTCIceCandidate, RTCIceServer

from eylo.pipelines.websocket.schemas import WSSessionState

if TYPE_CHECKING:
    from eylo.pipelines.webrtc.agent_peer import AgentPeerClient


class WebRTCNegotiationState(str, Enum):
    """Monotonic lifecycle for one tenant-bound negotiation."""

    PREPARING = "preparing"
    PREPARED = "prepared"
    ACQUIRING = "acquiring"
    ACTIVE = "active"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


@dataclass(frozen=True)
class WebRTCSessionKey:
    """Immutable WebRTC authority key."""

    organization_id: UUID
    session_id: str


@dataclass
class WebRTCSession:
    """Live state owned by the signaling manager, never serialized or persisted."""

    key: WebRTCSessionKey
    session_state: WSSessionState
    negotiation_id: str
    state: WebRTCNegotiationState = WebRTCNegotiationState.PREPARING
    ice_servers: tuple[RTCIceServer, ...] = ()
    negotiation_expires_at: float | None = None
    credential_expires_at: float | None = None
    peer_client: AgentPeerClient | None = None
    tts_streamer_task: asyncio.Task | None = None
    deadline_task: asyncio.Task | None = None
    answer_payload: dict[str, Any] | None = None
    offer_digest: str | None = None
    pending_candidates: list[RTCIceCandidate | None] = field(default_factory=list)
    candidate_digests: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    connected_at: float | None = None
    terminated_at: float | None = None

    @property
    def organization_id(self) -> UUID:
        return self.key.organization_id

    @property
    def session_id(self) -> str:
        return self.key.session_id

    def transition(self, state: WebRTCNegotiationState) -> None:
        self.state = state
        self.updated_at = time.time()
        if state is WebRTCNegotiationState.ACTIVE:
            self.connected_at = self.updated_at
        elif state is WebRTCNegotiationState.TERMINATED:
            self.terminated_at = self.updated_at
