"""Base classes and protocols for telephony providers.

This module defines the abstract interfaces that all telephony providers must implement,
enabling a pluggable architecture for different vendors (Twilio, Plivo, Exotel, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol, TypeAlias
from uuid import UUID

from eylo.common.contracts.telephony import CallEndedReason as CallEndedReason
from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendRetryable,
    OutboundSendTerminal,
    OutboundSendUnknown,
    OutboundTransportKind,
    require_failure_code,
)


class TelephonyProvider(str, Enum):
    """Supported telephony providers."""

    TWILIO = "twilio"
    PLIVO = "plivo"
    EXOTEL = "exotel"
    VONAGE = "vonage"


class AudioEncoding(str, Enum):
    """Audio encoding formats for telephony."""

    MULAW = "mulaw"
    ALAW = "alaw"
    LINEAR16 = "linear16"  # PCM LINEAR16 (Vonage)
    PCM_S16LE = "pcm_s16le"
    PCM_MULAW = "pcm_mulaw"


@dataclass
class TelephonyConfig:
    """Base configuration for telephony services."""

    provider: TelephonyProvider
    encoding: AudioEncoding = AudioEncoding.MULAW
    sample_rate: int = 8000
    channels: int = 1
    # Provider-specific config can be added here
    extra_config: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.extra_config is None:
            self.extra_config = {}


@dataclass
class CallMetadata:
    """Metadata for a telephony call."""

    call_sid: str
    call_id: Optional[UUID] = None
    stream_sid: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    organization_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    agent_revision: Optional[int] = None
    provider_config_id: Optional[UUID] = None
    provider_config_revision: Optional[int] = None
    conversation_id: Optional[UUID] = None
    direction: str = "INBOUND"  # INBOUND or OUTBOUND
    initial_message: Optional[str] = None
    media_stream_token: Optional[str] = None
    requires_media_stream_token: bool = False


@dataclass
class InboundMediaMessage:
    """Standardized inbound media message from any telephony provider."""

    event: str
    payload: bytes  # Raw audio bytes
    timestamp: str
    track: str = "inbound"
    sequence_number: Optional[str] = None


@dataclass
class OutboundMediaMessage:
    """Standardized outbound media message to any telephony provider."""

    payload: bytes  # Raw audio bytes
    stream_sid: str


class CarrierMediaStatus(str, Enum):
    """Observed result of a carrier-facing realtime media write."""

    ACCEPTED = "accepted"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CarrierMediaResult:
    """Safe typed projection of one carrier audio or buffer-control write."""

    status: CarrierMediaStatus
    bytes_count: int = 0
    failure_code: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status is CarrierMediaStatus.ACCEPTED


@dataclass(frozen=True, slots=True)
class TelephonyOperationCapabilities:
    """Provider guarantees that affect safe charged-operation replay."""

    provider_idempotency: bool
    reconciliation: bool


@dataclass(frozen=True, slots=True)
class TelephonyOperationProfile:
    """Static provider-operation metadata needed before durable send begins."""

    provider_operation: str
    transport_kind: OutboundTransportKind
    destination_origin: str
    capabilities: TelephonyOperationCapabilities

    def __post_init__(self) -> None:
        if not self.provider_operation.strip():
            raise ValueError("Telephony provider operation is required.")
        if not self.destination_origin.startswith("https://"):
            raise ValueError("Telephony provider destination must use HTTPS.")


@dataclass(frozen=True, slots=True)
class TelephonyControlAccepted:
    """The carrier accepted one live call-control operation."""

    status_code: int | None = None

    def __post_init__(self) -> None:
        _validate_control_status(self.status_code)


@dataclass(frozen=True, slots=True)
class _TelephonyControlFailure:
    failure_code: str
    status_code: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "failure_code",
            require_failure_code(self.failure_code),
        )
        _validate_control_status(self.status_code)


@dataclass(frozen=True, slots=True)
class TelephonyControlRejected(_TelephonyControlFailure):
    """The carrier explicitly rejected the requested control."""


@dataclass(frozen=True, slots=True)
class TelephonyControlUnknown(_TelephonyControlFailure):
    """The carrier may have applied the control; do not claim success."""


@dataclass(frozen=True, slots=True)
class TelephonyControlUnsupported(_TelephonyControlFailure):
    """The carrier adapter does not implement this control."""


TelephonyControlResult: TypeAlias = (
    TelephonyControlAccepted
    | TelephonyControlRejected
    | TelephonyControlUnknown
    | TelephonyControlUnsupported
)


def _validate_control_status(status_code: int | None) -> None:
    if status_code is not None and not 100 <= status_code <= 599:
        raise ValueError("Control status must be an HTTP status between 100 and 599.")


def classify_provider_failure(
    error: Exception,
    *,
    operation: str,
) -> OutboundSendOutcome:
    """Map provider failures without retaining or exposing vendor error prose."""
    status_code = _provider_status_code(error)
    failure_code = f"{operation}_rejected"
    if status_code == 429:
        return OutboundSendRetryable(
            failure_code=failure_code,
            status_code=status_code,
        )
    if status_code is not None and 400 <= status_code < 500 and status_code != 408:
        return OutboundSendTerminal(
            failure_code=failure_code,
            status_code=status_code,
        )
    return OutboundSendUnknown(
        failure_code=f"{operation}_unconfirmed",
        status_code=status_code,
    )


def classify_control_failure(
    error: Exception,
    *,
    operation: str,
) -> TelephonyControlRejected | TelephonyControlUnknown:
    """Map a live control failure without leaking provider response content."""
    status_code = _provider_status_code(error)
    if status_code is not None and 400 <= status_code < 500 and status_code != 408:
        return TelephonyControlRejected(
            failure_code=f"{operation}_rejected",
            status_code=status_code,
        )
    return TelephonyControlUnknown(
        failure_code=f"{operation}_unconfirmed",
        status_code=status_code,
    )


def _provider_status_code(error: Exception) -> int | None:
    for name in ("status_code", "status"):
        value = getattr(error, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value if 100 <= value <= 599 else None
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 100 <= value <= 599 else None
    return None


class TelephonyMessageParser(Protocol):
    """Protocol for parsing provider-specific messages."""

    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse raw message from provider."""
        ...

    def get_event_type(self, message: Dict[str, Any]) -> str:
        """Extract event type from parsed message."""
        ...

    def extract_media(self, message: Dict[str, Any]) -> Optional[InboundMediaMessage]:
        """Extract media data from message."""
        ...

    def extract_dtmf(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract inbound DTMF digits from message, when provider exposes them."""
        ...

    async def extract_metadata(self, message: Dict[str, Any]) -> Optional[CallMetadata]:
        """Extract call metadata from start message."""
        ...


class BaseTelephonyService(ABC):
    """Abstract base class for telephony service implementations."""

    def __init__(self, config: TelephonyConfig):
        """Initialize the telephony service.

        Args:
            config: Telephony configuration

        """
        self.config = config
        self._is_connected = False

    def set_websocket(self, websocket: Any) -> None:
        """Attach the active provider WebSocket to the service."""
        self.websocket = websocket
        self._is_connected = True

    @property
    def is_connected(self) -> bool:
        """Check if the service is connected."""
        return self._is_connected

    @property
    @abstractmethod
    def provider(self) -> TelephonyProvider:
        """Get the provider identifier."""
        ...

    @abstractmethod
    async def send_media(self, message: OutboundMediaMessage) -> None:
        """Send media (audio) to the provider.

        Args:
            message: Outbound media message

        """
        ...

    @abstractmethod
    async def send_clear(self, stream_sid: str) -> bool:
        """Send clear signal; return false only when the carrier lacks it."""
        ...

    @abstractmethod
    def build_twiml_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Build provider-specific XML/response for call control.

        Args:
            ws_url: WebSocket URL for media streaming
            custom_params: Custom parameters to pass

        Returns:
            Provider-specific response (e.g., TwiML for Twilio)

        """
        ...

    @abstractmethod
    def outbound_call_profile(self) -> TelephonyOperationProfile:
        """Describe outbound-call transport and retry guarantees."""
        ...

    @abstractmethod
    async def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        ws_url: str,
        custom_params: Dict[str, Any],
        authorization: OutboundSendAuthorization,
        status_callback_url: Optional[str] = None,
    ) -> OutboundSendOutcome:
        """Initiate an outbound call.

        Args:
            to_number: Destination phone number
            from_number: Source phone number
            ws_url: WebSocket URL for media streaming
            custom_params: Custom parameters
            status_callback_url: URL for call status updates

        Returns:
            Typed provider acceptance, rejection, retry, or ambiguity.

        """
        ...

    @abstractmethod
    def create_message_parser(self) -> TelephonyMessageParser:
        """Create a message parser for this provider.

        Returns:
            Provider-specific message parser

        """
        ...

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return provider-specific base configuration for audio processing."""

    @abstractmethod
    def get_output_format(self) -> Dict[str, Any]:
        """Return provider-specific TTS output_format metadata."""

    async def end_call(self, call_sid: str) -> TelephonyControlResult:
        """Terminate an active call by its provider call SID.

        Args:
            call_sid: The provider-specific call identifier

        Returns:
            Response data from the provider

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support end_call"
        )

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Transfer an active call to another number.

        Args:
            call_sid: The provider-specific call identifier
            to_number: Destination phone number in E.164 format

        Returns:
            Response data from the provider

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support transfer_call"
        )

    async def send_dtmf(
        self,
        call_sid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones on an active call.

        Args:
            call_sid: The provider-specific call identifier
            digits: DTMF digits to send (0-9, *, #, w for pause)

        Returns:
            Response data from the provider

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support send_dtmf"
        )

    async def connect(self) -> None:
        """Connect to the telephony service."""
        self._is_connected = True

    async def disconnect(self) -> None:
        """Disconnect from the telephony service."""
        self._is_connected = False
