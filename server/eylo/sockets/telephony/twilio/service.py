"""Twilio telephony service implementation.

This module implements the BaseTelephonyService interface for Twilio,
providing WebSocket media streaming and call control capabilities.
"""

import base64
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import WebSocket

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendSucceeded,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.sockets.telephony.base import (
    BaseTelephonyService,
    CallMetadata,
    InboundMediaMessage,
    OutboundMediaMessage,
    TelephonyConfig,
    TelephonyControlResult,
    TelephonyMessageParser,
    TelephonyOperationCapabilities,
    TelephonyOperationProfile,
    TelephonyProvider,
    classify_provider_failure,
)
from eylo.sockets.telephony.twilio.rest_client import TwilioRestClient

logger = logging.getLogger(__name__)


class TwilioMessageParser(TelephonyMessageParser):
    """Parser for Twilio-specific message formats."""

    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse raw JSON message from Twilio.

        Args:
            raw_message: Raw JSON string from Twilio WebSocket

        Returns:
            Parsed message dictionary

        """
        return json.loads(raw_message)

    def get_event_type(self, message: Dict[str, Any]) -> str:
        """Extract event type from Twilio message.

        Args:
            message: Parsed message dictionary

        Returns:
            Event type string

        """
        return message.get("event", "")

    def extract_media(self, message: Dict[str, Any]) -> Optional[InboundMediaMessage]:
        """Extract media data from Twilio media message.

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

        # Decode base64 to μ-law bytes
        payload = base64.b64decode(payload_b64)

        return InboundMediaMessage(
            event="media",
            payload=payload,
            timestamp=media_data.get("timestamp", ""),
            track=media_data.get("track", "inbound"),
            sequence_number=message.get("sequenceNumber"),
        )

    def extract_dtmf(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract Twilio inbound DTMF digits."""
        if message.get("event") != "dtmf":
            return None
        dtmf = message.get("dtmf", {}) or {}
        digit = dtmf.get("digit") or dtmf.get("digits")
        return str(digit) if digit else None

    async def extract_metadata(self, message: Dict[str, Any]) -> Optional[CallMetadata]:
        """Extract call metadata from Twilio start message.

        Args:
            message: Parsed message dictionary

        Returns:
            CallMetadata if this is a start event, None otherwise

        """
        if message.get("event") != "start":
            return None

        start_data = message.get("start", {})
        custom_params = start_data.get("customParameters", {})

        from uuid import UUID

        org_id = custom_params.get("OrgId")
        agent_id = custom_params.get("AgentId")
        requires_stream_token = any(
            key in custom_params
            for key in ("OrgId", "AgentId", "InitialMessage", "Direction")
        )

        return CallMetadata(
            call_sid=custom_params.get("CallSid", "") or start_data.get("callSid", ""),
            stream_sid=start_data.get("streamSid"),
            from_number=custom_params.get("From", ""),
            to_number=custom_params.get("To", ""),
            organization_id=UUID(org_id) if org_id else None,
            agent_id=UUID(agent_id) if agent_id else None,
            direction=custom_params.get("Direction", "INBOUND"),
            initial_message=custom_params.get("InitialMessage"),
            media_stream_token=custom_params.get("StreamToken")
            or custom_params.get("stream_token"),
            requires_media_stream_token=requires_stream_token,
        )


class TwilioService(BaseTelephonyService):
    """Twilio telephony service implementation."""

    def __init__(self, config: TelephonyConfig, websocket: Optional[WebSocket] = None):
        """Initialize Twilio service.

        Args:
            config: Telephony configuration
            websocket: Optional WebSocket connection for media streaming

        """
        super().__init__(config)
        self.websocket = websocket
        self._parser = TwilioMessageParser()

    @property
    def provider(self) -> TelephonyProvider:
        """Get the provider identifier.

        Returns:
            TelephonyProvider.TWILIO

        """
        return TelephonyProvider.TWILIO

    def set_websocket(self, websocket: WebSocket):
        """Set the WebSocket connection.

        Args:
            websocket: WebSocket connection

        """
        self.websocket = websocket
        self._is_connected = True

    async def send_media(self, message: OutboundMediaMessage) -> None:
        """Send media (audio) to Twilio via WebSocket.

        Args:
            message: Outbound media message

        """
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        # Encode audio to base64 for Twilio
        payload_b64 = base64.b64encode(message.payload).decode("utf-8")

        twilio_message = {
            "event": "media",
            "streamSid": message.stream_sid,
            "media": {
                "payload": payload_b64,
            },
        }

        await self.websocket.send_json(twilio_message)

    async def send_clear(self, stream_sid: str) -> bool:
        """Send clear signal to Twilio to empty audio buffer.

        Args:
            stream_sid: Stream identifier

        """
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        try:
            message = {
                "event": "clear",
                "streamSid": stream_sid,
            }
            await self.websocket.send_json(message)
            logger.debug(f"Sent Twilio clear event for stream {stream_sid}")
            return True

        except Exception:
            logger.warning("Twilio clear write failed.")
            raise

    def build_twiml_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Build TwiML response for Twilio call control.

        Args:
            ws_url: WebSocket URL for media streaming
            custom_params: Custom parameters to pass to the stream

        Returns:
            TwiML XML string

        """
        params_xml = []
        for k, v in custom_params.items():
            params_xml.append(f'<Parameter name="{k}" value="{quote(str(v))}" />')
        params_str = "\n".join(params_xml)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Connect>
        <Stream url="{ws_url}">
          {params_str}
        </Stream>
      </Connect>
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
        """Initiate an outbound call via Twilio REST API.

        Args:
            to_number: Destination phone number
            from_number: Source phone number
            ws_url: WebSocket URL for media streaming
            custom_params: Custom parameters
            status_callback_url: URL for call status updates

        Returns:
            Response data from Twilio API

        """
        del authorization  # Twilio Calls API exposes no client idempotency slot.
        twiml = self.build_twiml_response(ws_url, custom_params)
        client = self._make_rest_client()
        try:
            response = await client.create_call(
                to_number=to_number,
                from_number=from_number,
                twiml=twiml,
                status_callback_url=status_callback_url or "",
            )
        except Exception as error:  # noqa: BLE001 - adapter owns provider taxonomy
            return classify_provider_failure(error, operation="call_create")
        call_sid = str(response.get("sid") or "").strip()
        if not call_sid:
            return OutboundSendUnknown(failure_code="call_create_response_invalid")
        return OutboundSendSucceeded(
            provider_reference=call_sid,
            status_code=201,
        )

    def create_message_parser(self) -> TelephonyMessageParser:
        """Create a message parser for Twilio.

        Returns:
            TwilioMessageParser instance

        """
        return self._parser

    def get_config(self) -> Dict[str, Any]:
        """Return the Twilio baseline STT configuration."""
        return {"encoding": "mulaw", "sample_rate": 8000}

    def get_output_format(self) -> Dict[str, Any]:
        """Return the Twilio baseline TTS output format metadata."""
        return {
            "container": "raw",
            "encoding": "pcm_mulaw",
            "sample_rate": 8000,
        }

    async def disconnect(self) -> None:
        """Disconnect from Twilio service."""
        self._is_connected = False
        self.websocket = None

    def _make_rest_client(self):
        """Create a TwilioRestClient using per-org credentials from config."""
        extra = self.config.extra_config or {}
        return TwilioRestClient(
            account_sid=extra.get("account_sid"),
            auth_token=extra.get("auth_token"),
        )

    async def end_call(self, call_sid: str) -> TelephonyControlResult:
        """Terminate an active Twilio call.

        Args:
            call_sid: The Twilio Call SID

        Returns:
            Response data from Twilio API

        """
        return await self._make_rest_client().end_call(call_sid)

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Transfer an active Twilio call to another number.

        Args:
            call_sid: The Twilio Call SID
            to_number: Destination phone number in E.164 format

        Returns:
            Response data from Twilio API

        """
        return await self._make_rest_client().transfer_call(call_sid, to_number)

    async def send_dtmf(
        self,
        call_sid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones on an active Twilio call.

        Args:
            call_sid: The Twilio Call SID
            digits: DTMF digits to send

        Returns:
            Response data from Twilio API

        """
        return await self._make_rest_client().send_dtmf(call_sid, digits)

    def outbound_call_profile(self) -> TelephonyOperationProfile:
        return TelephonyOperationProfile(
            provider_operation="telephony.twilio.call.create",
            transport_kind=OutboundTransportKind.HTTP,
            destination_origin="https://api.twilio.com",
            capabilities=TelephonyOperationCapabilities(
                provider_idempotency=False,
                reconciliation=False,
            ),
        )
