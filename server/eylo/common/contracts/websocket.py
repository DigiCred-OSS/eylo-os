"""Neutral WebSocket envelopes shared by module and transport layers."""

from enum import Enum
from typing import Optional, Union
from uuid import UUID

import arrow
from pydantic import EmailStr, Field, SkipValidation

from eylo.common.schemas import EyloBaseApiSchema

WEBRTC_SIGNALING_VERSION = 1


class WsEventAction(str, Enum):
    """Stable event names on the Eylo WebSocket wire."""

    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    SESSION_INITIALIZED = "session:initialized"
    SESSION_CLOSED = "session:closed"
    CONVERSATION_CREATED = "conversation:created"
    CONVERSATION_UPDATED = "conversation:updated"
    CONVERSATION_QUERY = "conversation:query"
    CONVERSATION_READ = "conversation:read"
    AUDIO_CONFIG = "audio:config"
    AUDIO_DATA = "audio:data"
    VOICE_STATE = "voice:state"
    MESSAGE_CREATED = "message:created"
    MESSAGE_STATUS = "message:status"
    MESSAGE_TRANSCRIPT = "message:transcript"
    MESSAGE_QUERY = "message:query"
    MESSAGE_FEEDBACK = "message:feedback"
    CONTACT_IDENTIFIED = "contact:identified"
    CONTACT_UPDATED = "contact:updated"
    CONTACT_QUERY = "contact:query"
    PARTICIPANT_CREATED = "participant:created"
    PARTICIPANT_UPDATED = "participant:updated"
    PARTICIPANT_QUERY = "participant:query"
    AGENT_THINKING = "agent:thinking"
    AGENT_PROCESSING = "agent:processing"
    TOOL_EXECUTING = "tool:executing"
    TOOL_COMPLETED = "tool:completed"
    AGENT_RESPONSE_COMPLETE = "agent:response_complete"
    AUTH_REQUIRED = "auth:required"
    CONNECTION_STARTED = "connection:started"
    CONNECTION_SUCCESS = "connection:success"
    CONNECTION_FAILED = "connection:failed"
    RECORDING_CONSENT = "recording:consent"
    RECORDING_CONSENT_STATE = "recording:consent_state"
    WEBRTC_PREPARE = "webrtc:prepare"
    WEBRTC_OFFER = "webrtc:offer"
    WEBRTC_ANSWER = "webrtc:answer"
    WEBRTC_ICE_CANDIDATE = "webrtc:ice_candidate"
    WEBRTC_HANGUP = "webrtc:hangup"
    WEBRTC_PEER_CREATED = "webrtc:peer_created"
    WEBRTC_PEER_CONNECTING = "webrtc:peer_connecting"
    WEBRTC_PEER_CONNECTED = "webrtc:peer_connected"
    WEBRTC_PEER_DISCONNECTED = "webrtc:peer_disconnected"
    WEBRTC_PEER_FAILED = "webrtc:peer_failed"
    WEBRTC_ICE_GATHERING = "webrtc:ice_gathering"
    WEBRTC_ICE_COMPLETE = "webrtc:ice_complete"
    WEBRTC_TRACK_ADDED = "webrtc:track_added"
    WEBRTC_TRACK_REMOVED = "webrtc:track_removed"
    STT_CONNECTING = "stt:connecting"
    STT_CONNECTED = "stt:connected"
    STT_READY = "stt:ready"
    STT_DISCONNECTED = "stt:disconnected"
    STT_ERROR = "stt:error"
    TTS_CONNECTING = "tts:connecting"
    TTS_CONNECTED = "tts:connected"
    TTS_READY = "tts:ready"
    TTS_DISCONNECTED = "tts:disconnected"
    TTS_ERROR = "tts:error"
    CALL_STARTED = "call:started"
    CALL_RINGING = "call:ringing"
    CALL_CONNECTED = "call:connected"
    CALL_ENDED = "call:ended"
    CALL_TRANSFERRING = "call:transferring"
    CALL_TRANSFERRED = "call:transferred"
    SYSTEM_MESSAGE = "system"
    ACK = "system:ack"


class WsEvent(EyloBaseApiSchema):
    """Base fields shared by WebSocket requests and responses."""

    request_id: Optional[str] = None
    timestamp: float = Field(default_factory=lambda: arrow.utcnow().timestamp())


class WsIdentifyEvent(WsEvent):
    """Identify event to associate contact with session."""

    id: Optional[UUID] = None
    name: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    external_id: Optional[str] = None
    preferences: Optional[dict[str, str]] = {}


class WsRequestEvent(WsEvent):
    """Container for one client WebSocket event."""

    kind: WsEventAction
    timestamp: float = Field(default_factory=lambda: arrow.utcnow().timestamp())
    data: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> "WsRequestEvent":
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> "WsRequestEvent":
        return cls.model_validate_json(json_str)


class WsResponse(WsEvent):
    """Server response envelope for one WebSocket event."""

    status: SkipValidation[int] = 200
    kind: WsEventAction
    organization_id: UUID
    session_id: str
    data: Optional[Union[dict, list[dict]]] = None
    version: str = "1.0"


def build_ws_error_response(
    event: WsRequestEvent | None,
    *,
    organization_id: UUID,
    session_id: str,
    message: str | None = None,
    status_code: int = 500,
) -> WsResponse:
    """Build a correlated error without reflecting the untrusted request body."""
    return WsResponse(
        status=status_code,
        kind=WsEventAction.ERROR,
        data={"message": message or "The event is not valid or not supported."},
        organization_id=organization_id,
        session_id=session_id,
        request_id=event.request_id if event else None,
    )


class WsCommonFilters(EyloBaseApiSchema):
    external_ids: list[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=100, ge=1, le=1000)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class WsConversationQueryFilters(WsCommonFilters):
    """Conversation selection shared by nested WebSocket queries."""

    conversation_ids: list[UUID] = Field(default_factory=list)
    message_limit: int = Field(
        default=1,
        ge=0,
        le=500,
        description="Number of messages to include per conversation (0=none, for list view use 1)",
    )
    message_offset: int = Field(
        default=0,
        ge=0,
        description="Offset for message pagination (for loading older messages)",
    )


class WsConversationQueryEvent(WsEvent):
    """Event to query conversation details."""

    filters: WsConversationQueryFilters = Field(
        default_factory=WsConversationQueryFilters
    )


class WsConversationReadEvent(EyloBaseApiSchema):
    """Mark one contact-owned conversation read through the current message set."""

    conversation_id: UUID


class WsParticipantQueryFilters(WsConversationQueryFilters):
    participant_ids: list[UUID] = Field(default_factory=list)


class WsParticipantQueryEvent(WsEvent):
    filters: WsParticipantQueryFilters = Field(
        default_factory=WsParticipantQueryFilters
    )


class WsContactQueryFilters(WsConversationQueryFilters):
    """Filters for querying contacts."""

    contact_ids: list[UUID] = Field(default_factory=list)


class WsContactQueryEvent(WsEvent):
    """Event to query contacts."""

    filters: WsContactQueryFilters = Field(default_factory=WsContactQueryFilters)
