"""Exotel telephony service implementation (stub).

This module provides a stub implementation for Exotel telephony service.
Complete implementation to be added when Exotel integration is needed.
"""

import base64
import html
import json
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import aiohttp
from fastapi import HTTPException, WebSocket

from eylo.common.contracts.phone_numbers import PhoneNumberNormalizationService
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
)

logger = logging.getLogger(__name__)


class ExotelMessageParser(TelephonyMessageParser):
    """Parser for Exotel-specific message formats."""

    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse raw message from Exotel.

        Args:
            raw_message: Raw message from Exotel WebSocket

        Returns:
            Parsed message dictionary

        """
        return json.loads(raw_message)

    def get_event_type(self, message: Dict[str, Any]) -> str:
        """Extract event type from Exotel message.

        Args:
            message: Parsed message dictionary

        Returns:
            Event type string

        """
        event = message.get("event", "unknown")
        return event

    def extract_media(self, message: Dict[str, Any]) -> Optional[InboundMediaMessage]:
        """Extract media data from Exotel message.

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

        # Decode base64 to raw audio bytes (Linear16 PCM)
        payload = base64.b64decode(payload_b64)
        timestamp = media_data.get("timestamp", "")
        track = media_data.get("track", "inbound")
        sequence_number = media_data.get("sequence_number", 0)

        return InboundMediaMessage(
            event="media",
            payload=payload,
            timestamp=timestamp,
            track=track,
            sequence_number=sequence_number,
        )

    def extract_dtmf(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract Exotel inbound DTMF digits."""
        if message.get("event") not in {"dtmf", "digits"}:
            return None
        data = message.get("dtmf") or message.get("digits") or message
        if isinstance(data, dict):
            digits = data.get("digit") or data.get("digits")
        else:
            digits = data
        return str(digits) if digits else None

    async def extract_metadata(self, message: Dict[str, Any]) -> Optional[CallMetadata]:
        """Extract call metadata from Exotel message.

        Args:
            message: Parsed message dictionary

        Returns:
            CallMetadata if this is a start event, None otherwise

        """
        if message.get("event") != "start":
            return None

        logger.debug("Extracting metadata from Exotel message: %s", message)

        start_data = message.get("start", {})
        call_sid = start_data.get("call_sid", "")
        stream_sid = message.get("stream_sid", "")
        from_number = start_data.get("from", "")
        to_number = start_data.get("to", "")
        raw_custom_params = start_data.get("custom_parameters", {}) or {}
        custom_params = dict(raw_custom_params)

        logger.debug("Extracted custom parameters: %s", raw_custom_params)

        # Handle cases where Exotel puts the CustomField JSON in the key (often HTML-escaped)
        for k, v in raw_custom_params.items():
            if isinstance(k, str):
                key_unescaped = html.unescape(k)
                if key_unescaped.startswith("{") and key_unescaped.endswith("}"):
                    try:
                        decoded = json.loads(key_unescaped)
                        if isinstance(decoded, dict):
                            custom_params.update(decoded)
                            logger.debug(
                                "Merged CustomField from key payload: %s", decoded
                            )
                    except json.JSONDecodeError:
                        logger.error("Failed to decode CustomField from key: %s", k)

        # Exotel Passthru can return CustomField either as:
        # - custom_parameters["CustomField"] = "<json>"
        # - custom_parameters["<json>"] = "" (observed)
        # Simplified: we now expect minimal CustomField (activity_id, flow_type).
        custom_field_str = raw_custom_params.get(
            "CustomField"
        ) or raw_custom_params.get("customfield")
        if isinstance(custom_field_str, str):
            try:
                decoded = json.loads(html.unescape(custom_field_str))
                if isinstance(decoded, dict):
                    custom_params.update(decoded)
            except json.JSONDecodeError:
                logger.error("Failed to decode Exotel CustomField value")

        org_id = custom_params.get("org_id") or custom_params.get("OrgId")
        agent_id = custom_params.get("agent_id") or custom_params.get("AgentId")
        custom_routing_present = any(
            key in custom_params
            for key in (
                "org_id",
                "OrgId",
                "agent_id",
                "AgentId",
                "InitialMessage",
                "initial_message",
                "Direction",
                "direction",
            )
        )
        direction = (
            custom_params.get("direction")
            or custom_params.get("Direction")
            or "INBOUND"
        )
        initial_message = custom_params.get("InitialMessage") or custom_params.get(
            "initial_message"
        )
        media_stream_token = custom_params.get("StreamToken") or custom_params.get(
            "stream_token"
        )

        conversation_id: UUID | None = None

        logger.debug(
            "[EXOTEL:SERVICE] start.custom_parameters merged=%s org_id=%s agent_id=%s",
            custom_params,
            org_id,
            agent_id,
        )

        if not from_number or not to_number:
            raise ValueError("From and To numbers are required")

        phone_norm_service = PhoneNumberNormalizationService()
        from_result = phone_norm_service.parse_to_e164(from_number)
        to_result = phone_norm_service.parse_to_e164(to_number)
        if not from_result.success or not to_result.success:
            raise ValueError("From and To numbers must be valid phone numbers")

        from_number = from_result.e164
        to_number = to_result.e164
        if not from_number or not to_number:
            raise ValueError("Phone number normalization returned no E.164 value")

        if initial_message is None:
            initial_message = "Hello"

        return CallMetadata(
            call_sid=call_sid,
            stream_sid=stream_sid,
            from_number=from_number,
            to_number=to_number,
            organization_id=UUID(org_id) if org_id else None,
            agent_id=UUID(agent_id) if agent_id else None,
            conversation_id=conversation_id,
            direction=direction,
            initial_message=initial_message,
            media_stream_token=media_stream_token,
            requires_media_stream_token=custom_routing_present,
        )


class ExotelService(BaseTelephonyService):
    """Exotel telephony service implementation (stub)."""

    def __init__(self, config: TelephonyConfig, websocket: Optional[WebSocket] = None):
        """Initialize Exotel service.

        Args:
            config: Telephony configuration
            websocket: Optional WebSocket connection for media streaming

        """
        super().__init__(config)
        self.websocket = websocket
        self._parser = ExotelMessageParser()

    @property
    def provider(self) -> TelephonyProvider:
        """Get the provider identifier.

        Returns:
            TelephonyProvider.EXOTEL

        """
        return TelephonyProvider.EXOTEL

    def set_websocket(self, websocket: WebSocket):
        """Set the WebSocket connection.

        Args:
            websocket: WebSocket connection

        """
        self.websocket = websocket
        self._is_connected = True

    async def send_media(self, message: OutboundMediaMessage) -> None:
        """Send raw PCM audio to Exotel."""
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        # Convert raw bytes to base64
        payload_b64 = base64.b64encode(message.payload).decode("utf-8")

        # Construct JSON message
        msg = {
            "event": "media",
            "sequence_number": str(int(time.time())),
            "stream_sid": message.stream_sid,
            "media": {
                "payload": payload_b64,
                "timestamp": str(int(time.time() * 1000)),
            },
        }

        try:
            await self.websocket.send_text(json.dumps(msg))
        except Exception:
            logger.warning("Exotel media write failed.")
            raise

    async def send_clear(self, stream_sid: str) -> bool:
        if not self.websocket:
            raise RuntimeError("Telephony WebSocket is not connected.")

        msg = {"event": "clear", "stream_sid": stream_sid}

        try:
            await self.websocket.send_text(json.dumps(msg))
            return True
        except Exception:
            logger.warning("Exotel clear write failed.")
            raise

    def build_twiml_response(
        self,
        ws_url: str,
        custom_params: Dict[str, Any],
    ) -> str:
        """Return JSON bootstrap payload.

        Exotel Voicebot applets accept either a static WSS URL or an HTTPS endpoint that
        responds with {"url": "wss://..."}. We follow the latter so we can inject
        per-call query params (tokens, org IDs, etc.).
        """
        final_url = ws_url
        if custom_params:
            from urllib.parse import urlencode

            query = urlencode(custom_params)
            separator = "&" if "?" in final_url else "?"
            final_url = f"{final_url}{separator}{query}"

        return json.dumps({"url": final_url})

    async def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        ws_url: str,
        custom_params: Dict[str, Any],
        authorization: OutboundSendAuthorization,
        status_callback_url: Optional[str] = None,
    ) -> OutboundSendOutcome:
        """Make outbound call connecting to an Applet.

        Args:
            to_number: Destination phone number
            from_number: Source phone number
            ws_url: WebSocket URL for media streaming
            custom_params: Custom parameters
            status_callback_url: URL for call status updates

        Returns:
            Response data from Exotel API

        """
        del authorization, ws_url  # Exotel exposes no client idempotency slot.

        if not self.config.extra_config:
            return OutboundSendTerminal(failure_code="call_create_not_configured")

        # 1. Get Credentials/config
        api_key = self.config.extra_config.get("api_key")
        api_token = self.config.extra_config.get("api_token")
        account_sid = self.config.extra_config.get("account_sid")
        app_id = self.config.extra_config.get("exotel_app_id")

        if not all([api_key, api_token, account_sid, app_id]):
            return OutboundSendTerminal(failure_code="call_create_not_configured")

        phone_norm_service = PhoneNumberNormalizationService()

        # 2. Construct flow URL
        # Exotel docs specify my.exotel.com for the flow URL regardless of cluster.
        applet_url = f"http://my.exotel.com/{account_sid}/exoml/start_voice/{app_id}"
        # Exotel requires Url to be an HTTP applet.
        flow_url = applet_url
        custom_field_value: Optional[str] = None
        if custom_params:
            # Prefer pre-packed CustomField if caller provided one.
            custom_field_value = custom_params.get("CustomField") or custom_params.get(
                "custom_field_value"
            )

        # 3. Call Exotel REST API
        subdomain = self.config.extra_config.get("subdomain")
        url = f"https://{subdomain}/v1/Accounts/{account_sid}/Calls/connect.json"

        # Format numbers per Exotel expectations
        from_formatted = phone_norm_service.format_for_exotel(from_number)
        to_formatted = to_number  # E.164 accepted for customer leg

        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(api_key, api_token),
                timeout=timeout,
            ) as session:
                data = {
                    # Exotel expects:
                    # - From: the customer/destination number
                    # - CallerId: your Exotel number / agent number
                    "From": to_formatted,
                    "CallerId": from_formatted,
                    "Url": flow_url,
                    "CallType": "trans",
                    "TimeLimit": 15 * 60,
                }
                if custom_field_value:
                    data["CustomField"] = custom_field_value
                if status_callback_url:
                    data["StatusCallback"] = status_callback_url

                async with session.post(url, data=data) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        if resp.status == 429:
                            return OutboundSendRetryable(
                                failure_code="call_create_rejected",
                                status_code=resp.status,
                            )
                        if resp.status < 500 and resp.status != 408:
                            return OutboundSendTerminal(
                                failure_code="call_create_rejected",
                                status_code=resp.status,
                            )
                        return OutboundSendUnknown(
                            failure_code="call_create_unconfirmed",
                            status_code=resp.status,
                        )
                    payload = json.loads(text) if text else {}
                    call = payload.get("Call") if isinstance(payload, dict) else None
                    call_sid = str(
                        (call or {}).get("Sid")
                        or payload.get("CallSid")
                        or payload.get("sid")
                        or ""
                    ).strip()
                    if not call_sid:
                        return OutboundSendUnknown(
                            failure_code="call_create_response_invalid",
                            status_code=resp.status,
                        )
                    logger.info("Initiated Exotel call")
                    return OutboundSendSucceeded(
                        provider_reference=call_sid,
                        status_code=resp.status,
                    )
        except Exception:  # noqa: BLE001 - transport ambiguity forbids resend
            logger.warning("Exotel call initiation outcome is unconfirmed")
            return OutboundSendUnknown(failure_code="call_create_unconfirmed")

    def create_message_parser(self) -> TelephonyMessageParser:
        """Create a message parser for Exotel.

        Returns:
            ExotelMessageParser instance

        """
        return ExotelMessageParser()

    def get_config(self) -> Dict[str, Any]:
        """Return the Exotel baseline STT configuration."""
        return {"encoding": "linear16", "sample_rate": 8000}

    def get_output_format(self) -> Dict[str, Any]:
        return {
            "container": "raw",
            "encoding": "pcm_s16le",  # LINEAR16
            "sample_rate": 8000,
        }

    async def end_call(self, call_sid: str) -> TelephonyControlResult:
        """Terminate an active Exotel call.

        Args:
            call_sid: The Exotel Call SID

        Returns:
            Response data from Exotel API

        """
        if not self.config.extra_config:
            raise ValueError("Missing Exotel credentials")

        api_key = self.config.extra_config.get("api_key")
        api_token = self.config.extra_config.get("api_token")
        account_sid = self.config.extra_config.get("account_sid")

        if not all([api_key, api_token, account_sid]):
            raise ValueError("Missing Exotel credentials for end_call")

        subdomain = str(self.config.extra_config.get("subdomain") or "").strip()
        if not subdomain:
            raise ValueError("Missing Exotel API host for end_call")
        url = f"https://{subdomain}/v1/Accounts/{account_sid}/Calls/{call_sid}.json"

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(api_key, api_token),
                timeout=timeout,
            ) as session:
                async with session.post(url, data={"Status": "completed"}) as resp:
                    if resp.status >= 300:
                        return classify_control_failure(
                            HTTPException(status_code=resp.status),
                            operation="call_end",
                        )
                    return TelephonyControlAccepted(status_code=resp.status)
        except (TimeoutError, aiohttp.ClientError):
            logger.warning("Exotel call end outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_end_unconfirmed")
        except Exception as error:  # noqa: BLE001 - provider failure taxonomy
            return classify_control_failure(error, operation="call_end")

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Return explicit unsupported for Exotel live transfer."""
        del call_sid, to_number
        return TelephonyControlUnsupported(failure_code="call_transfer_unsupported")

    async def send_dtmf(
        self,
        call_sid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones on an active Exotel call."""
        if not self.config.extra_config:
            raise ValueError("Missing Exotel credentials")

        api_key = self.config.extra_config.get("api_key")
        api_token = self.config.extra_config.get("api_token")
        account_sid = self.config.extra_config.get("account_sid")

        if not all([api_key, api_token, account_sid]):
            raise ValueError("Missing Exotel credentials for send_dtmf")

        subdomain = str(self.config.extra_config.get("subdomain") or "").strip()
        if not subdomain:
            raise ValueError("Missing Exotel API host for send_dtmf")
        url = (
            f"https://{subdomain}/v1/Accounts/{account_sid}/Calls/{call_sid}/SendDtmf/"
        )

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(api_key, api_token),
                timeout=timeout,
            ) as session:
                async with session.post(
                    url,
                    data={"Digits": digits, "Leg": "aleg"},
                ) as resp:
                    if resp.status >= 300:
                        return classify_control_failure(
                            HTTPException(status_code=resp.status),
                            operation="call_dtmf",
                        )
                    return TelephonyControlAccepted(status_code=resp.status)
        except (TimeoutError, aiohttp.ClientError):
            logger.warning("Exotel DTMF outcome is unconfirmed")
            return TelephonyControlUnknown(failure_code="call_dtmf_unconfirmed")
        except Exception as error:  # noqa: BLE001 - provider failure taxonomy
            return classify_control_failure(error, operation="call_dtmf")

    def outbound_call_profile(self) -> TelephonyOperationProfile:
        host = str((self.config.extra_config or {}).get("subdomain") or "").strip()
        if not host:
            raise ValueError("Exotel API host is required.")
        return TelephonyOperationProfile(
            provider_operation="telephony.exotel.call.create",
            transport_kind=OutboundTransportKind.HTTP,
            destination_origin=f"https://{host}",
            capabilities=TelephonyOperationCapabilities(
                provider_idempotency=False,
                reconciliation=False,
            ),
        )
