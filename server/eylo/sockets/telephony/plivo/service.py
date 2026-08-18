"""Plivo telephony service implementation.

This module implements the BaseTelephonyService interface for Plivo,
providing WebSocket audio streaming and call control capabilities.

Based on real-world implementations:
- https://github.com/bolna-ai/bolna (production Plivo integration)
- https://www.plivo.com/docs/voice/api/audio-stream/

WebSocket Message Format:
- Start event: {"event": "start", "start": {"streamId": "...", "callId": "...", ...}}
- Media event: {"event": "media", "media": {"payload": "base64_mulaw", "timestamp": "..."}}
- Stop event: {"event": "stop"}
- PlayAudio (outbound): {"event": "playAudio", "media": {"payload": "base64", "sampleRate": "8000", "contentType": "audio/x-mulaw"}}
- ClearAudio (interruption): {"event": "clearAudio", "streamId": "..."}
- Checkpoint (mark): {"event": "checkpoint", "streamId": "...", "name": "..."}

Audio Format: μ-law @ 8kHz (same as Twilio)
"""

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.sockets.telephony.base import (
    BaseTelephonyService,
    CallMetadata,
    InboundMediaMessage,
    OutboundMediaMessage,
    TelephonyConfig,
    TelephonyControlAccepted,
    TelephonyControlResult,
    TelephonyControlUnknown,
    TelephonyControlUnsupported,
    TelephonyMessageParser,
    TelephonyOperationCapabilities,
    TelephonyOperationProfile,
    TelephonyProvider,
    classify_control_failure,
    classify_provider_failure,
)

logger = logging.getLogger(__name__)


class PlivoMessageParser(TelephonyMessageParser):
    """Parser for Plivo-specific WebSocket message formats.

    Plivo WebSocket Protocol (based on production implementations):
    - Start: {"event": "start", "start": {"streamId": "...", "callId": "...", ...}}
    - Media: {"event": "media", "media": {"payload": "base64_mulaw", "timestamp": "..."}}
    - Stop: {"event": "stop"}
    - Checkpoint: {"event": "checkpoint", "name": "..."}

    Audio: μ-law @ 8kHz (same as Twilio)
    """

    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse raw JSON message from Plivo WebSocket.

        Args:
            raw_message: Raw JSON string from Plivo WebSocket

        Returns:
            Parsed message dictionary

        Example:
            {"event": "media", "media": {"payload": "...", "timestamp": "..."}}

        """
        return json.loads(raw_message)

    def get_event_type(self, message: Dict[str, Any]) -> str:
        """Extract event type from Plivo message.

        Args:
            message: Parsed message dictionary

        Returns:
            Event type string ("start", "media", "stop", "checkpoint")

        """
        return message.get("event", "")

    def extract_media(self, message: Dict[str, Any]) -> Optional[InboundMediaMessage]:
        """Extract media data from Plivo media event.

        Plivo media format (from bolna-ai):
        {
            "event": "media",
            "media": {
                "payload": "base64_encoded_mulaw_audio",
                "timestamp": "1234567890"
            }
        }

        Args:
            message: Parsed message dictionary

        Returns:
            InboundMediaMessage if this is a media event, None otherwise

        """
        if message.get("event") != "media":
            return None

        media_data = message.get("media", {})
        payload_b64 = media_data.get("payload", "")

        if not payload_b64:
            return None

        try:
            # Decode base64 to μ-law bytes
            payload = base64.b64decode(payload_b64)
        except Exception as error:
            logger.error(
                "Failed to decode Plivo audio payload error_type=%s",
                type(error).__name__,
            )
            return None

        return InboundMediaMessage(
            event="media",
            payload=payload,
            timestamp=media_data.get("timestamp", ""),
            track=media_data.get("track", "inbound"),
            sequence_number=message.get("sequenceNumber"),
        )

    def extract_dtmf(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract Plivo inbound DTMF digits."""
        if message.get("event") not in {"dtmf", "digits"}:
            return None
        data = message.get("dtmf") or message.get("digits") or message
        if isinstance(data, dict):
            digits = data.get("digit") or data.get("digits")
        else:
            digits = data
        return str(digits) if digits else None

    async def extract_metadata(self, message: Dict[str, Any]) -> Optional[CallMetadata]:
        """Extract call metadata from Plivo start event.

        Plivo start format (from bolna-ai production code):
        {
            "event": "start",
            "start": {
                "streamId": "550e8400-...",
                "callId": "78737f83-...",
                "from": "+1234567890",
                "to": "+0987654321"
            }
        }

        Args:
            message: Parsed message dictionary

        Returns:
            CallMetadata if this is a start event, None otherwise

        """
        if message.get("event") != "start":
            return None

        start_data = message.get("start", {})

        # Plivo uses callId (not callUuid) and streamId
        call_id = start_data.get("callId", "")
        stream_id = start_data.get("streamId", "")

        return CallMetadata(
            call_sid=call_id,  # Plivo's callId maps to call_sid
            stream_sid=stream_id,
            from_number=start_data.get("from", ""),
            to_number=start_data.get("to", ""),
        )


class PlivoService(BaseTelephonyService):
    """Plivo telephony service implementation.

    Provides real-time audio streaming and call control using Plivo's
    WebSocket-based Audio Stream API.

    Based on production implementation from bolna-ai.
    """

    def __init__(self, config: TelephonyConfig, websocket: Optional[Any] = None):
        """Initialize Plivo service with REST client.

        Args:
            config: Telephony configuration containing auth credentials
            websocket: Optional WebSocket connection for media streaming

        """
        super().__init__(config)
        self.websocket = websocket
        self._parser = PlivoMessageParser()

        # Extract credentials from extra_config
        extra_config = config.extra_config or {}
        auth_id = extra_config.get("account_sid") or extra_config.get("auth_id")
        auth_token = extra_config.get("auth_token")

        if not auth_id or not auth_token:
            logger.warning("Plivo credentials not found in config.extra_config")
            logger.info("Will skip Plivo REST client initialization")
            self.client = None
            return

        try:
            import plivo

            self.client = plivo.RestClient(
                auth_id=auth_id,
                auth_token=auth_token,
            )
            logger.info("Plivo client initialized successfully")
        except ImportError:
            logger.error("Plivo SDK not installed. Install with: pip install plivo")
            self.client = None
        except Exception as error:
            logger.error(
                "Failed to initialize Plivo client error_type=%s",
                type(error).__name__,
            )
            self.client = None

    @property
    def provider(self) -> TelephonyProvider:
        """Get the provider identifier.

        Returns:
            TelephonyProvider.PLIVO

        """
        return TelephonyProvider.PLIVO

    def set_websocket(self, websocket: Any):
        """Set the WebSocket connection.

        Args:
            websocket: WebSocket connection

        """
        self.websocket = websocket
        self._is_connected = True

    async def send_media(self, message: OutboundMediaMessage) -> None:
        """Send audio media to Plivo WebSocket stream.

        Plivo playAudio event format (from bolna-ai):
        {
            "event": "playAudio",
            "media": {
                "contentType": "audio/x-mulaw",
                "sampleRate": "8000",
                "payload": "base64_encoded_audio"
            }
        }

        Args:
            message: Outbound media message with audio payload

        """
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        try:
            # Encode to base64
            payload_b64 = base64.b64encode(message.payload).decode("utf-8")

            plivo_message = {
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": "8000",
                    "payload": payload_b64,
                },
            }

            await self.websocket.send_json(plivo_message)

        except Exception:
            logger.warning("Plivo media write failed.")
            raise

    def build_twiml_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Build Plivo XML response with Stream element.

        Plivo XML format (from bolna-ai production):
        <Response>
            <Stream bidirectional="true" keepCallAlive="true">
                wss://your-server.com/stream
            </Stream>
        </Response>

        Args:
            ws_url: WebSocket URL for streaming
            custom_params: Custom parameters (can be encoded in URL)

        Returns:
            Plivo XML string

        """
        try:
            from plivo import plivoxml

            response = plivoxml.ResponseElement()

            # Add custom parameters to URL if needed
            final_url = ws_url
            if custom_params:
                # Encode params in URL query string
                import urllib.parse

                query_params = urllib.parse.urlencode(custom_params)
                separator = "&" if "?" in ws_url else "?"
                final_url = f"{ws_url}{separator}{query_params}"

            # Configure Stream element (simplified from bolna-ai)
            stream = plivoxml.StreamElement(
                final_url,
                bidirectional="true",
                keepCallAlive="true",
            )

            response.add(stream)

            return response.to_string()

        except Exception as error:
            logger.error(
                "Failed to build Plivo XML error_type=%s",
                type(error).__name__,
            )
            # Fallback to simple XML string
            final_url = ws_url
            if custom_params:
                import urllib.parse

                query_params = urllib.parse.urlencode(custom_params)
                separator = "&" if "?" in ws_url else "?"
                final_url = f"{ws_url}{separator}{query_params}"

            return f"""<Response>
    <Stream bidirectional="true" keepCallAlive="true">{final_url}</Stream>
</Response>"""

    async def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        ws_url: str,
        custom_params: Dict[str, Any],
        authorization: OutboundSendAuthorization,
        status_callback_url: Optional[str] = None,
    ) -> OutboundSendOutcome:
        """Initiate an outbound call via Plivo REST API.

        Plivo requires answer_url to be an HTTP endpoint that returns XML.
        We point it to our /api/voice/plivo/answer callback which returns
        Plivo XML with a <Stream> element pointing to the ws_url.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (Plivo number)
            ws_url: WebSocket URL for streaming
            custom_params: Custom parameters
            status_callback_url: Optional callback URL for call events

        Returns:
            Response data from Plivo API containing call_uuid

        """
        del authorization  # Plivo Calls API exposes no client idempotency slot.
        if not self.client:
            return OutboundSendTerminal(failure_code="call_create_not_configured")

        try:
            from urllib.parse import quote, urlparse

            # Derive HTTP answer_url from ws_url's domain
            parsed = urlparse(ws_url)
            server_domain = parsed.hostname or ""
            answer_url = (
                f"https://{server_domain}/api/voice/plivo/answer"
                f"?ws_url={quote(ws_url, safe='')}"
            )

            call_params = {
                "from_": from_number,
                "to_": to_number,
                "answer_url": answer_url,
                "answer_method": "GET",
            }

            if status_callback_url:
                call_params["hangup_url"] = status_callback_url
                call_params["hangup_method"] = "POST"

            response = await asyncio.to_thread(self.client.calls.create, **call_params)

            call_uuid = response[0] if isinstance(response, tuple) else response

            call_uuid = str(call_uuid).strip()
            if not call_uuid:
                return OutboundSendUnknown(failure_code="call_create_response_invalid")
            logger.info("Initiated Plivo call")
            return OutboundSendSucceeded(provider_reference=call_uuid)

        except Exception as error:  # noqa: BLE001 - adapter owns provider taxonomy
            logger.warning("Plivo call initiation failed")
            return classify_provider_failure(error, operation="call_create")

    def create_message_parser(self) -> TelephonyMessageParser:
        """Create a message parser for Plivo.

        Returns:
            PlivoMessageParser instance

        """
        return self._parser

    async def send_clear(self, stream_sid: str) -> bool:
        """Send clear signal to Plivo to empty audio buffer.

        Args:
            stream_sid: Stream identifier

        """
        await self.clear_stream(stream_sid)
        return True

    async def clear_stream(self, stream_sid: str) -> None:
        """Clear Plivo stream buffer (interrupt audio playback).

        Plivo clearAudio event format (from bolna-ai):
        {
            "event": "clearAudio",
            "streamId": "..."
        }

        Args:
            stream_sid: Stream identifier

        """
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        try:
            message = {
                "event": "clearAudio",
                "streamId": stream_sid,
            }
            await self.websocket.send_json(message)
            logger.debug(f"Cleared Plivo stream: {stream_sid}")

        except Exception:
            logger.warning("Plivo clear write failed.")
            raise

    def get_config(self) -> Dict[str, Any]:
        """Return the Plivo baseline STT configuration."""
        return {"encoding": "mulaw", "sample_rate": 8000}

    def get_output_format(self) -> Dict[str, Any]:
        """Return the Plivo baseline TTS output format metadata."""
        return {
            "container": "raw",
            "encoding": "pcm_mulaw",
            "sample_rate": 8000,
        }

    async def send_checkpoint(self, stream_sid: str, mark_id: str) -> None:
        """Send checkpoint event (Plivo's equivalent of Twilio's mark).

        Plivo checkpoint format (from bolna-ai):
        {
            "event": "checkpoint",
            "streamId": "...",
            "name": "..."
        }

        Args:
            stream_sid: Stream identifier
            mark_id: Checkpoint/mark identifier

        """
        if not self.websocket:
            logger.warning("Cannot send checkpoint: WebSocket not connected")
            return

        try:
            message = {
                "event": "checkpoint",
                "streamId": stream_sid,
                "name": mark_id,
            }
            await self.websocket.send_json(message)
            logger.debug(f"Sent Plivo checkpoint: {mark_id}")

        except Exception as error:
            logger.error(
                "Failed to send Plivo checkpoint error_type=%s",
                type(error).__name__,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from Plivo service."""
        self._is_connected = False
        self.websocket = None

    async def end_call(self, call_sid: str) -> TelephonyControlResult:
        """Terminate an active Plivo call.

        Uses Plivo's DELETE /Call/{uuid}/ API to hang up the call.
        Ref: https://www.plivo.com/docs/voice/api/call/#delete-a-call

        Args:
            call_sid: Plivo call UUID

        Returns:
            Response data confirming call hangup

        """
        if not self.client:
            raise RuntimeError("Plivo client not initialized. Check credentials.")

        try:
            # Plivo SDK is synchronous — run in thread to avoid blocking the event loop
            await asyncio.wait_for(
                asyncio.to_thread(self.client.calls.delete, call_sid),
                timeout=20,
            )
            logger.info("Ended Plivo call")
            return TelephonyControlAccepted()
        except TimeoutError:
            logger.warning("Plivo call end outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_end_unconfirmed")
        except Exception as error:  # noqa: BLE001 - SDK failure taxonomy
            return classify_control_failure(error, operation="call_end")

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Return explicit unsupported until Eylo hosts a signed answer URL."""
        del call_sid, to_number
        return TelephonyControlUnsupported(failure_code="call_transfer_unsupported")

    async def send_dtmf(
        self,
        call_sid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones on an active Plivo call.

        Uses Plivo's DTMF API to send keypad tones.
        Ref: https://www.plivo.com/docs/voice/api/call/#send-digits-on-a-call

        Args:
            call_sid: Plivo call UUID
            digits: DTMF digits to send (0-9, *, #)

        Returns:
            Response data from Plivo API

        """
        if not self.client:
            raise RuntimeError("Plivo client not initialized. Check credentials.")

        try:
            # Plivo SDK is synchronous — run in thread to avoid blocking the event loop
            await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.calls.send_digits,
                    call_sid,
                    digits=digits,
                ),
                timeout=20,
            )
            logger.info("Sent DTMF to Plivo call")
            return TelephonyControlAccepted()
        except TimeoutError:
            logger.warning("Plivo DTMF outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_dtmf_unconfirmed")
        except Exception as error:  # noqa: BLE001 - SDK failure taxonomy
            return classify_control_failure(error, operation="call_dtmf")

    def outbound_call_profile(self) -> TelephonyOperationProfile:
        return TelephonyOperationProfile(
            provider_operation="telephony.plivo.call.create",
            transport_kind=OutboundTransportKind.PROVIDER_SDK,
            destination_origin="https://api.plivo.com",
            capabilities=TelephonyOperationCapabilities(
                provider_idempotency=False,
                reconciliation=False,
            ),
        )
