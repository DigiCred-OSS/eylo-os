"""Vonage telephony service implementation.

This module implements the BaseTelephonyService interface for Vonage,
providing WebSocket audio streaming and call control via NCCO.

Based on vocode-core production implementation:
- https://github.com/vocodedev/vocode-core/tree/main/vocode/streaming/telephony/conversation/vonage_phone_conversation.py
- https://github.com/vocodedev/vocode-core/tree/main/vocode/streaming/telephony/client/vonage_client.py

Key Differences from Twilio/Plivo:
- Audio Format: LINEAR16 @ 16kHz (vs μ-law @ 8kHz)
- Protocol: Binary WebSocket frames (vs JSON events)
- Call Control: NCCO JSON (vs TwiML XML)
- No mark/checkpoint events (simplified protocol)
"""

import json
import logging
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import jwt
from fastapi import HTTPException, WebSocket

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendRetryable,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.sockets.telephony.base import (
    AudioEncoding,
    BaseTelephonyService,
    CallMetadata,
    InboundMediaMessage,
    OutboundMediaMessage,
    TelephonyConfig,
    TelephonyControlAccepted,
    TelephonyControlResult,
    TelephonyControlUnknown,
    TelephonyMessageParser,
    TelephonyOperationCapabilities,
    TelephonyOperationProfile,
    TelephonyProvider,
    classify_control_failure,
)

logger = logging.getLogger(__name__)

# Vonage audio constants (from vocode-core)
VONAGE_SAMPLING_RATE = 16000  # 16kHz
VONAGE_AUDIO_ENCODING = AudioEncoding.LINEAR16
VONAGE_CHUNK_SIZE = 640  # 20ms at 16kHz with 16-bit samples (640 bytes)
VONAGE_CONTENT_TYPE = "audio/l16;rate=16000"
PCM_SILENCE_BYTE = b"\x00"


class _VonageApplicationClient:
    """Minimal application JWT signer for the async Voice API calls below."""

    def __init__(self, *, application_id: str, private_key: str) -> None:
        self._application_id = application_id
        self._private_key = private_key

    def generate_application_jwt(self) -> str:
        issued_at = int(time.time())
        return jwt.encode(
            {
                "application_id": self._application_id,
                "iat": issued_at,
                "exp": issued_at + 60,
                "jti": str(uuid4()),
            },
            self._private_key,
            algorithm="RS256",
        )


class VonageMessageParser(TelephonyMessageParser):
    """Parser for Vonage binary audio protocol.

    Unlike Twilio/Plivo which use JSON events, Vonage streams raw binary
    LINEAR16 audio over WebSocket. This parser handles the binary protocol.

    WebSocket Protocol:
    - First message: JSON start message (optional, server-sent)
    - Subsequent messages: Raw LINEAR16 audio bytes
    - No JSON events for media/stop/checkpoint
    """

    def __init__(self):
        """Initialize parser."""
        self._call_started = False
        self._metadata: Optional[CallMetadata] = None

    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse message from Vonage WebSocket.

        Vonage can send JSON for initial handshake, but most messages
        are binary audio. This method handles JSON when present.

        Args:
            raw_message: Raw message (JSON or binary indicator)

        Returns:
            Parsed message dictionary

        """
        try:
            return json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            # Not JSON - probably binary audio frame indicator
            return {"event": "binary_audio"}

    def parse_binary_message(self, raw_bytes: bytes) -> InboundMediaMessage:
        """Parse binary audio message from Vonage.

        Args:
            raw_bytes: Raw LINEAR16 audio bytes

        Returns:
            InboundMediaMessage with LINEAR16 payload

        """
        return InboundMediaMessage(
            event="media",
            payload=raw_bytes,
            timestamp="",  # Vonage doesn't include timestamps in binary frames
            track="inbound",
        )

    def get_event_type(self, message: Dict[str, Any]) -> str:
        """Extract event type from message.

        Args:
            message: Parsed message dictionary

        Returns:
            Event type string

        """
        return message.get("event", "")

    def extract_media(self, message: Dict[str, Any]) -> Optional[InboundMediaMessage]:
        """Extract media from binary audio.

        For Vonage, media extraction is handled by parse_binary_message
        since audio comes as raw WebSocket binary frames.

        Args:
            message: Parsed message dictionary

        Returns:
            None (use parse_binary_message for binary frames)

        """
        # Binary audio is handled separately via parse_binary_message
        return None

    def extract_dtmf(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract Vonage inbound DTMF digits from JSON control messages."""
        if message.get("event") not in {"dtmf", "input"}:
            return None
        digits = message.get("digits") or message.get("dtmf")
        if isinstance(digits, dict):
            digits = digits.get("digits") or digits.get("digit")
        return str(digits) if digits else None

    async def extract_metadata(self, message: Dict[str, Any]) -> Optional[CallMetadata]:
        """Extract call metadata.

        Vonage doesn't send explicit start events in WebSocket.
        Metadata comes from the HTTP webhook (answer_url).

        Args:
            message: Parsed message dictionary

        Returns:
            CallMetadata if available, None otherwise

        """
        # Vonage metadata comes from HTTP webhook, not WebSocket
        # WebSocket connection is established after answer_url returns NCCO
        return self._metadata

    def set_metadata(self, metadata: CallMetadata):
        """Set call metadata from HTTP webhook.

        Args:
            metadata: Call metadata from answer_url webhook

        """
        self._metadata = metadata
        self._call_started = True


class VonageService(BaseTelephonyService):
    """Vonage telephony service implementation.

    Provides real-time LINEAR16 audio streaming at 16kHz via WebSocket
    and call control using NCCO (Nexmo Call Control Objects).

    Audio Format:
    - Encoding: LINEAR16 (PCM signed 16-bit little-endian)
    - Sample Rate: 16000 Hz
    - Chunk Size: 640 bytes (20ms)
    - Content-Type: audio/l16;rate=16000
    """

    def __init__(self, config: TelephonyConfig, websocket: Optional[WebSocket] = None):
        """Initialize Vonage service with REST client.

        Args:
            config: Telephony configuration containing Vonage credentials
            websocket: Optional WebSocket connection for audio streaming

        """
        # Override config for Vonage-specific settings
        config.encoding = VONAGE_AUDIO_ENCODING
        config.sample_rate = VONAGE_SAMPLING_RATE

        super().__init__(config)
        self.websocket = websocket
        self._parser = VonageMessageParser()

        # Extract Vonage credentials from extra_config
        extra_config = config.extra_config or {}
        api_key = extra_config.get("api_key")
        api_secret = extra_config.get("api_secret")
        application_id = extra_config.get("application_id")
        private_key = extra_config.get("private_key")

        if not all([api_key, api_secret, application_id, private_key]):
            logger.warning("Vonage credentials incomplete in config.extra_config")
            logger.info("Will skip Vonage REST client initialization")
            self.client = None
            return

        try:
            self.client = _VonageApplicationClient(
                application_id=application_id,
                private_key=private_key,
            )
            logger.info("Vonage client initialized successfully")
        except Exception as error:
            logger.error(
                "Failed to initialize Vonage client error_type=%s",
                type(error).__name__,
            )
            self.client = None

    @property
    def provider(self) -> TelephonyProvider:
        """Get the provider identifier.

        Returns:
            TelephonyProvider.VONAGE

        """
        return TelephonyProvider.VONAGE

    def set_websocket(self, websocket: WebSocket):
        """Set the WebSocket connection.

        Args:
            websocket: WebSocket connection for audio streaming

        """
        self.websocket = websocket
        self._is_connected = True

    async def send_media(self, message: OutboundMediaMessage) -> None:
        """Send LINEAR16 audio to Vonage via binary WebSocket.

        Vonage expects raw LINEAR16 audio bytes, not JSON-wrapped payloads.
        Audio is sent as binary WebSocket frames.

        Args:
            message: Outbound media message with LINEAR16 audio

        """
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        try:
            # Pad odd-length chunks with silence (Vonage requirement)
            payload = message.payload
            if len(payload) % 2 == 1:
                payload += PCM_SILENCE_BYTE

            # Send raw binary audio (no JSON wrapper)
            await self.websocket.send_bytes(payload)

        except Exception:
            logger.warning("Vonage media write failed.")
            raise

    async def send_clear(self, stream_sid: str) -> bool:
        """Send clear signal to Vonage.

        Note: Vonage WebSocket protocol does not support a standard 'clear' event
        like Twilio/Plivo. This is a no-op for now.

        Args:
            stream_sid: Stream identifier

        """
        # Vonage doesn't have a direct equivalent in its binary WebSocket protocol
        # We might need to use the REST API to stop/restart media if strictly necessary,
        # but for now we'll just log it.
        logger.debug("Vonage 'send_clear' not supported via WebSocket - skipping")
        return False

    def build_ncco_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Build NCCO (Nexmo Call Control Object) response for Vonage.

        NCCO is a JSON array of actions that control the call.
        For WebSocket streaming, we use the "connect" action.

        Example NCCO:
        [
            {
                "action": "connect",
                "endpoint": [{
                    "type": "websocket",
                    "uri": "wss://example.com/socket",
                    "content-type": "audio/l16;rate=16000",
                    "headers": {}
                }]
            }
        ]

        Args:
            ws_url: WebSocket URL for audio streaming
            custom_params: Custom parameters (encoded in URL or headers)

        Returns:
            NCCO JSON string

        """
        # Build WebSocket endpoint
        final_url = ws_url
        if custom_params:
            # Encode params in URL query string
            import urllib.parse

            query_params = urllib.parse.urlencode(custom_params)
            separator = "&" if "?" in ws_url else "?"
            final_url = f"{ws_url}{separator}{query_params}"

        # Build NCCO
        ncco = [
            {
                "action": "connect",
                "endpoint": [
                    {
                        "type": "websocket",
                        "uri": final_url,
                        "content-type": VONAGE_CONTENT_TYPE,
                        "headers": {},
                    }
                ],
            }
        ]

        return json.dumps(ncco)

    def build_twiml_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Alias for build_ncco_response to satisfy BaseTelephonyService interface.

        Args:
            ws_url: WebSocket URL for audio streaming
            custom_params: Custom parameters

        Returns:
            NCCO JSON string

        """
        return self.build_ncco_response(ws_url, custom_params)

    async def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        ws_url: str,
        custom_params: Dict[str, Any],
        authorization: OutboundSendAuthorization,
        status_callback_url: Optional[str] = None,
    ) -> OutboundSendOutcome:
        """Initiate an outbound call via Vonage Voice API.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (Vonage number)
            ws_url: WebSocket URL for audio streaming
            custom_params: Custom parameters
            status_callback_url: Optional URL for call status events

        Returns:
            Response data from Vonage API containing uuid

        Raises:
            RuntimeError: If Vonage client not initialized or call fails

        """
        del authorization  # Vonage Voice API exposes no client idempotency slot.
        if not self.client:
            return OutboundSendTerminal(failure_code="call_create_not_configured")

        try:
            # Build NCCO for WebSocket streaming
            ncco_str = self.build_ncco_response(ws_url, custom_params)
            ncco = json.loads(ncco_str)

            # Build call request
            call_data = {
                "to": [{"type": "phone", "number": to_number}],
                "from": {"type": "phone", "number": from_number},
                "ncco": ncco,
            }

            # Add event URL if provided
            if status_callback_url:
                call_data["event_url"] = [status_callback_url]

            # Make REST API call using aiohttp (async)
            import aiohttp

            jwt_token = self.client.generate_application_jwt()

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://api.nexmo.com/v1/calls",
                    json=call_data,
                    headers={"Authorization": f"Bearer {jwt_token}"},
                ) as response:
                    if not response.ok:
                        await response.read()
                        if response.status == 429:
                            return OutboundSendRetryable(
                                failure_code="call_create_rejected",
                                status_code=response.status,
                            )
                        if 400 <= response.status < 500 and response.status != 408:
                            return OutboundSendTerminal(
                                failure_code="call_create_rejected",
                                status_code=response.status,
                            )
                        return OutboundSendUnknown(
                            failure_code="call_create_unconfirmed",
                            status_code=response.status,
                        )

                    response_data = await response.json()

                    vonage_uuid = str(response_data.get("uuid") or "").strip()
                    if response_data.get("status") != "started" or not vonage_uuid:
                        return OutboundSendUnknown(
                            failure_code="call_create_response_invalid",
                            status_code=response.status,
                        )
                    logger.info("Initiated Vonage call")
                    return OutboundSendSucceeded(
                        provider_reference=vonage_uuid,
                        status_code=response.status,
                    )

        except Exception:  # noqa: BLE001 - transport ambiguity forbids resend
            logger.warning("Vonage call initiation outcome is unconfirmed")
            return OutboundSendUnknown(failure_code="call_create_unconfirmed")

    async def end_call(self, call_uuid: str) -> TelephonyControlResult:
        """End an active Vonage call.

        Args:
            call_uuid: Vonage call UUID

        Returns:
            Response data confirming call hangup

        Raises:
            RuntimeError: If Vonage client not initialized or request fails

        """
        if not self.client:
            raise RuntimeError("Vonage client not initialized. Check credentials.")

        try:
            import aiohttp

            jwt_token = self.client.generate_application_jwt()

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(
                    f"https://api.nexmo.com/v1/calls/{call_uuid}",
                    json={"action": "hangup"},
                    headers={"Authorization": f"Bearer {jwt_token}"},
                ) as response:
                    if not response.ok:
                        return classify_control_failure(
                            HTTPException(status_code=response.status),
                            operation="call_end",
                        )

                    logger.info("Ended Vonage call")
                    return TelephonyControlAccepted(status_code=response.status)

        except (TimeoutError, aiohttp.ClientError):
            logger.warning("Vonage call end outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_end_unconfirmed")
        except Exception as error:  # noqa: BLE001 - JWT/provider failure taxonomy
            return classify_control_failure(error, operation="call_end")

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Transfer an active Vonage call to another number.

        Uses NCCO transfer action to connect the call to a new phone number.

        Args:
            call_sid: Vonage call UUID
            to_number: Destination phone number in E.164 format

        Returns:
            Response data from Vonage API

        """
        ncco = [
            {
                "action": "connect",
                "endpoint": [{"type": "phone", "number": to_number}],
            }
        ]
        return await self.update_call(call_sid, ncco)

    async def send_dtmf(
        self,
        call_uuid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones to Vonage call.

        Args:
            call_uuid: Vonage call UUID
            digits: DTMF digits to send (0-9, *, #)

        Returns:
            Response data confirming DTMF sent

        Raises:
            RuntimeError: If Vonage client not initialized or request fails

        """
        if not self.client:
            raise RuntimeError("Vonage client not initialized. Check credentials.")

        try:
            import aiohttp

            jwt_token = self.client.generate_application_jwt()

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(
                    f"https://api.nexmo.com/v1/calls/{call_uuid}/dtmf",
                    json={"digits": digits},
                    headers={"Authorization": f"Bearer {jwt_token}"},
                ) as response:
                    if not response.ok:
                        return classify_control_failure(
                            HTTPException(status_code=response.status),
                            operation="call_dtmf",
                        )

                    logger.debug("Sent DTMF to Vonage call")
                    return TelephonyControlAccepted(status_code=response.status)

        except (TimeoutError, aiohttp.ClientError):
            logger.warning("Vonage DTMF outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_dtmf_unconfirmed")
        except Exception as error:  # noqa: BLE001 - JWT/provider failure taxonomy
            return classify_control_failure(error, operation="call_dtmf")

    async def update_call(
        self,
        call_uuid: str,
        ncco: list,
    ) -> TelephonyControlResult:
        """Update an active call with new NCCO actions.

        Used for transferring calls or changing call flow.

        Args:
            call_uuid: Vonage call UUID
            ncco: New NCCO actions (as list of dicts)

        Returns:
            True if successful

        Raises:
            RuntimeError: If Vonage client not initialized or request fails

        """
        if not self.client:
            raise RuntimeError("Vonage client not initialized. Check credentials.")

        try:
            import aiohttp

            jwt_token = self.client.generate_application_jwt()

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(
                    f"https://api.nexmo.com/v1/calls/{call_uuid}",
                    json={
                        "action": "transfer",
                        "destination": {"type": "ncco", "ncco": ncco},
                    },
                    headers={"Authorization": f"Bearer {jwt_token}"},
                ) as response:
                    if not response.ok:
                        return classify_control_failure(
                            HTTPException(status_code=response.status),
                            operation="call_transfer",
                        )

                    logger.info("Updated Vonage call")
                    return TelephonyControlAccepted(status_code=response.status)

        except (TimeoutError, aiohttp.ClientError):
            logger.warning("Vonage call transfer outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_transfer_unconfirmed")
        except Exception as error:  # noqa: BLE001 - JWT/provider failure taxonomy
            return classify_control_failure(error, operation="call_transfer")

    def create_message_parser(self) -> TelephonyMessageParser:
        """Create a message parser for Vonage.

        Returns:
            VonageMessageParser instance

        """
        return self._parser

    async def receive_binary_audio(self, audio_bytes: bytes) -> InboundMediaMessage:
        """Receive and parse binary audio from Vonage WebSocket.

        Args:
            audio_bytes: Raw LINEAR16 audio bytes from WebSocket

        Returns:
            InboundMediaMessage with parsed audio

        """
        return self._parser.parse_binary_message(audio_bytes)

    async def disconnect(self) -> None:
        """Disconnect from Vonage service."""
        self._is_connected = False
        self.websocket = None

    def get_config(self) -> Dict[str, Any]:
        """Return provider-specific base configuration for audio processing."""
        return {"encoding": "linear16", "sample_rate": 16000}

    def get_output_format(self) -> Dict[str, Any]:
        """Return provider-specific TTS output format metadata."""
        return {
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": 16000,
        }

    def outbound_call_profile(self) -> TelephonyOperationProfile:
        return TelephonyOperationProfile(
            provider_operation="telephony.vonage.call.create",
            transport_kind=OutboundTransportKind.HTTP,
            destination_origin="https://api.nexmo.com",
            capabilities=TelephonyOperationCapabilities(
                provider_idempotency=False,
                reconciliation=False,
            ),
        )
