"""In-memory call sessions for telephony pipeline orchestration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from eylo.pipelines.voice.audio_transport import StreamingAudioTranscoder
from eylo.pipelines.voice.live_buffer import LiveVoiceBuffer
from eylo.pipelines.voice.stt import STTRealtime
from eylo.pipelines.voice.tts import TTSRealtime
from eylo.sockets.telephony.base import CallEndedReason


@dataclass
class CallSession:
    call_sid: str
    call_id: Optional[UUID] = None
    stream_sid: Optional[str] = None
    organization_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    agent_revision: Optional[int] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    conversation_id: Optional[UUID] = None
    user_session_id: Optional[UUID] = None
    audio_profile: str = "phone"
    # Pointers to realtime services
    stt: Optional[STTRealtime] = None
    tts: Optional[TTSRealtime] = None
    tts_audio_transcoder: Optional[StreamingAudioTranscoder] = None
    telephony_manager: Optional[Any] = None
    # Queues and tasks for monitoring
    stt_request_queue: Optional[asyncio.Queue] = None
    stt_response_queue: Optional[asyncio.Queue] = None
    tts_request_queue: Optional[asyncio.Queue] = None
    tts_response_queue: Optional[asyncio.Queue] = None
    stt_tasks: Dict[str, asyncio.Task] = field(default_factory=dict)
    tts_tasks: Dict[str, asyncio.Task] = field(default_factory=dict)
    policy_tasks: Dict[str, asyncio.Task] = field(default_factory=dict)
    tts_interrupt_event: asyncio.Event = field(default_factory=asyncio.Event)
    # Simple flags
    is_active: bool = True
    first_media_received: bool = False
    # Call ended reason tracking
    ended_reason: Optional[CallEndedReason] = None
    # Session routing and tracking
    auth_session_token: Optional[str] = None
    direction: str = "inbound"
    provider: Optional[str] = None
    provider_config_id: Optional[UUID] = None
    provider_config_revision: Optional[int] = None
    started_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    # Arbitrary metadata (e.g. campaign_id, campaign_contact_id)
    extra_data: Dict[str, str] = field(default_factory=dict)
    # Voice config (VoiceConfig from voice module, typed as Any to avoid circular import)
    voice_config: Optional[Any] = None
    # Voice recording (non-blocking audio capture)
    # Notification state mirrors WSSessionState. It never gates the recorder;
    # it records whether the configured disclosure was delivered.
    recording_consent_state: str = "not_required"
    audio_recorder: Optional[Any] = None
    # Durable voice_sessions row id, set once transcript projection starts.
    voice_session_id: Optional[UUID] = None
    live_voice_buffer: Optional[LiveVoiceBuffer] = None
    live_voice_turn_runner: Optional[Any] = None
    opener_text: Optional[str] = None
    carrier_audio_chunks: int = 0
    carrier_audio_bytes: int = 0
    comfort_audio_chunks: int = 0
    comfort_audio_bytes: int = 0
    finalization_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    termination_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    termination_requested: bool = False
    finalized: bool = False
    manager_closed_ws: bool = False


@dataclass(frozen=True, slots=True)
class MediaSessionKey:
    """Immutable identity for one organization-owned carrier media session."""

    organization_id: UUID
    provider: str
    call_sid: str


class CallSessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[MediaSessionKey, CallSession] = {}

    @staticmethod
    def key_for(session: CallSession) -> MediaSessionKey:
        if session.organization_id is None or session.provider is None:
            raise ValueError("Media session identity is incomplete.")
        return MediaSessionKey(
            organization_id=session.organization_id,
            provider=session.provider,
            call_sid=session.call_sid,
        )

    def publish(self, session: CallSession) -> None:
        """Publish one fully initialized session without overwriting another."""
        key = self.key_for(session)
        if key in self._sessions:
            raise ValueError("Media session identity is already active.")
        self._sessions[key] = session

    def find_by_provider_call(
        self,
        provider: str,
        call_sid: str,
        *,
        organization_id: UUID | None = None,
    ) -> Optional[CallSession]:
        matches = [
            session
            for key, session in self._sessions.items()
            if key.provider == provider
            and key.call_sid == call_sid
            and (organization_id is None or key.organization_id == organization_id)
        ]
        if len(matches) > 1:
            raise ValueError("Carrier call identity is ambiguous across organizations.")
        return matches[0] if matches else None

    def remove(self, session: CallSession) -> None:
        self._sessions.pop(self.key_for(session), None)

    def active_sessions(self) -> tuple[CallSession, ...]:
        return tuple(self._sessions.values())

    def resolve_session_id(
        self,
        provider: str,
        call_sid: str,
        organization_id: UUID,
    ) -> Optional[str]:
        """Resolve the WS-routable session_id for a call_sid.

        Returns auth_session_token if the call is still active in memory,
        otherwise None (caller should fall back to DB lookup).
        """
        sess = self.find_by_provider_call(
            provider,
            call_sid,
            organization_id=organization_id,
        )
        if sess and sess.auth_session_token:
            return sess.auth_session_token
        return None


S_CALLS = CallSessionRegistry()
