"""Schemas for Twilio Media Streams WebSocket messages."""

from typing import List, Optional, Union

from pydantic import BaseModel


class MediaFormat(BaseModel):
    """Media format information."""

    encoding: str
    sampleRate: int
    channels: int


class CustomParameters(BaseModel):
    """Custom parameters passed to the stream."""

    CallSid: Optional[str] = None
    From: Optional[str] = None
    To: Optional[str] = None
    OrgId: Optional[str] = None
    AgentId: Optional[str] = None
    InitialMessage: Optional[str] = None
    Direction: Optional[str] = None

    # Allow additional custom parameters
    class Config:
        extra = "allow"


class StartMessageData(BaseModel):
    """Data structure for the start message."""

    accountSid: str
    streamSid: str
    callSid: str
    tracks: List[str]
    mediaFormat: MediaFormat
    customParameters: Optional[CustomParameters] = None


class ConnectedMessage(BaseModel):
    """Schema for the connected message."""

    event: str
    protocol: str
    version: str


class StartMessage(BaseModel):
    """Schema for the start message."""

    event: str
    sequenceNumber: str
    start: StartMessageData
    streamSid: str


class MediaMessageData(BaseModel):
    """Data structure for the media message."""

    track: str
    chunk: str
    timestamp: str
    payload: str


class MediaMessage(BaseModel):
    """Schema for the media message."""

    event: str
    sequenceNumber: str
    media: MediaMessageData
    streamSid: str


class StopMessageData(BaseModel):
    """Data structure for the stop message."""

    accountSid: str
    callSid: str


class StopMessage(BaseModel):
    """Schema for the stop message."""

    event: str
    sequenceNumber: str
    stop: StopMessageData
    streamSid: str


class DTMFMessageData(BaseModel):
    """Data structure for the DTMF message."""

    track: str
    digit: str


class DTMFMessage(BaseModel):
    """Schema for the DTMF message."""

    event: str
    sequenceNumber: str
    dtmf: DTMFMessageData
    streamSid: str


class MarkMessageData(BaseModel):
    """Data structure for the mark message."""

    name: str


class MarkMessage(BaseModel):
    """Schema for the mark message."""

    event: str
    sequenceNumber: str
    streamSid: str
    mark: MarkMessageData


class ClearMessage(BaseModel):
    """Schema for the clear message."""

    event: str
    streamSid: str


# Outbound messages (sent to Twilio)
class OutboundMediaMessage(BaseModel):
    """Schema for outbound media messages sent to Twilio."""

    event: str
    streamSid: str
    media: MediaMessageData


class OutboundMarkMessage(BaseModel):
    """Schema for outbound mark messages sent to Twilio."""

    event: str
    streamSid: str
    mark: MarkMessageData


# Union type for handling all inbound message types
TwilioInboundMessage = Union[
    ConnectedMessage, StartMessage, MediaMessage, StopMessage, DTMFMessage, MarkMessage
]
