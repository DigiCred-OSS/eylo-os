"""Perform authenticated Twilio call-control REST requests."""

import base64
import logging
import re
from xml.sax.saxutils import escape as xml_escape

import httpx
from fastapi import HTTPException

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendUnknown,
)
from eylo.sockets.telephony.base import (
    TelephonyControlAccepted,
    TelephonyControlResult,
    TelephonyControlUnknown,
    TelephonyOperationProfile,
    classify_control_failure,
)
from eylo.sockets.telephony.number_purchase import (
    classify_number_purchase_status,
    decode_number_purchase_response,
    number_purchase_profile,
    number_purchase_success,
    number_purchase_transport_unknown,
)
from eylo.sockets.telephony.twilio.endpoint import twilio_account_url

logger = logging.getLogger(__name__)


class TwilioRestClient:
    """A simple async client for interacting with the Twilio REST API.

    Args:
        account_sid: Twilio Account SID. Required.
        auth_token: Twilio Auth Token. Required.

    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.base_url = twilio_account_url(self.account_sid)
        self._auth_header = self._prepare_auth_header()

    def _prepare_auth_header(self) -> str:
        """Prepares the Basic authentication header."""
        auth_str = f"{self.account_sid}:{self.auth_token}".encode()
        return f"Basic {base64.b64encode(auth_str).decode()}"

    async def create_call(
        self, to_number: str, from_number: str, twiml: str, status_callback_url: str
    ) -> dict:
        """Initiates an outbound call using the Twilio API.

        Args:
            to_number: The phone number to call.
            from_number: The Twilio phone number to call from.
            twiml: The TwiML to execute upon call connection.
            status_callback_url: The URL for call status webhooks.

        Returns:
            The JSON response from the Twilio API.

        Raises:
            HTTPException: If the API call to Twilio fails.

        """
        form_data = {
            "To": to_number,
            "From": from_number,
            "Twiml": twiml,
            "StatusCallback": status_callback_url,
            "StatusCallbackMethod": "POST",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{self.base_url}/Calls.json"
            try:
                resp = await client.post(
                    url,
                    data=form_data,
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if resp.status_code >= 300:
                    logger.error(
                        "Twilio call creation failed: status=%d",
                        resp.status_code,
                    )
                    raise HTTPException(
                        min(resp.status_code, 502),
                        f"Twilio call creation failed (status {resp.status_code}). Check provider credentials and account status.",
                    )

                return resp.json()
            except httpx.RequestError:
                logger.warning("Twilio call creation transport failed")
                raise HTTPException(
                    status_code=502,
                    detail="Unable to reach Twilio. Please try again.",
                )

    async def end_call(self, call_sid: str) -> TelephonyControlResult:
        """Terminate an active call.

        Args:
            call_sid: The Twilio Call SID to terminate.

        Returns:
            The JSON response from the Twilio API.

        Raises:
            HTTPException: If the API call to Twilio fails.

        """
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{self.base_url}/Calls/{call_sid}.json"
            try:
                resp = await client.post(
                    url,
                    data={"Status": "completed"},
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if resp.status_code >= 300:
                    return classify_control_failure(
                        HTTPException(status_code=resp.status_code),
                        operation="call_end",
                    )

                return TelephonyControlAccepted(status_code=resp.status_code)
            except httpx.RequestError:
                logger.warning("Twilio call end outcome is unconfirmed")
                return TelephonyControlUnknown(failure_code="call_end_unconfirmed")

    async def transfer_call(
        self,
        call_sid: str,
        to_number: str,
    ) -> TelephonyControlResult:
        """Transfer an active call to another number using TwiML update.

        Args:
            call_sid: The Twilio Call SID to transfer.
            to_number: Destination phone number in E.164 format.

        Returns:
            The JSON response from the Twilio API.

        """
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>{xml_escape(to_number)}</Dial>
</Response>"""

        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{self.base_url}/Calls/{call_sid}.json"
            try:
                resp = await client.post(
                    url,
                    data={"Twiml": twiml},
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if resp.status_code >= 300:
                    return classify_control_failure(
                        HTTPException(status_code=resp.status_code),
                        operation="call_transfer",
                    )

                return TelephonyControlAccepted(status_code=resp.status_code)
            except httpx.RequestError:
                logger.warning("Twilio call transfer outcome is unconfirmed")
                return TelephonyControlUnknown(failure_code="call_transfer_unconfirmed")

    async def send_dtmf(
        self,
        call_sid: str,
        digits: str,
    ) -> TelephonyControlResult:
        """Send DTMF tones on an active call using TwiML update.

        Args:
            call_sid: The Twilio Call SID.
            digits: DTMF digits to send (0-9, *, #, w for 0.5s pause).

        Returns:
            The JSON response from the Twilio API.

        """
        if not re.match(r"^[0-9*#wW]+$", digits):
            raise ValueError("Invalid DTMF digit sequence")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play digits="{xml_escape(digits)}"/>
</Response>"""

        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{self.base_url}/Calls/{call_sid}.json"
            try:
                resp = await client.post(
                    url,
                    data={"Twiml": twiml},
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if resp.status_code >= 300:
                    return classify_control_failure(
                        HTTPException(status_code=resp.status_code),
                        operation="call_dtmf",
                    )

                return TelephonyControlAccepted(status_code=resp.status_code)
            except httpx.RequestError:
                logger.warning("Twilio DTMF outcome is unconfirmed")
                return TelephonyControlUnknown(failure_code="call_dtmf_unconfirmed")

    async def search_available_numbers(
        self,
        country: str,
        number_type: str = "Local",
        area_code: str | None = None,
        contains: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search for available phone numbers to purchase.

        Args:
            country: ISO 3166-1 alpha-2 country code (e.g. "US", "GB").
            number_type: One of "Local", "TollFree", "Mobile".
            area_code: Optional area code filter.
            contains: Optional pattern the number should contain.
            limit: Max results to return (1-30).

        Returns:
            List of available number dicts from Twilio.

        """
        params: dict[str, str | int] = {"PageSize": min(limit, 30)}
        if area_code:
            params["AreaCode"] = area_code
        if contains:
            params["Contains"] = contains

        url = f"{self.base_url}/AvailablePhoneNumbers/{country}/{number_type}.json"

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": self._auth_header},
                )

                if resp.status_code >= 300:
                    logger.error(
                        "Twilio number search failed: status=%d", resp.status_code
                    )
                    raise HTTPException(
                        min(resp.status_code, 502),
                        f"Twilio search failed (status {resp.status_code}). Check provider credentials and account status.",
                    )

                data = resp.json()
                return data.get("available_phone_numbers", [])
            except httpx.RequestError:
                logger.warning("Twilio number search transport failed")
                raise HTTPException(
                    status_code=502,
                    detail="Unable to reach Twilio. Please try again.",
                )

    def purchase_profile(self) -> TelephonyOperationProfile:
        return number_purchase_profile("twilio", "https://api.twilio.com")

    async def purchase_number(
        self,
        phone_number: str,
        *,
        authorization: OutboundSendAuthorization,
        country: str | None = None,
    ) -> OutboundSendOutcome:
        """Purchase (provision) a phone number on Twilio.

        Args:
            phone_number: E.164 phone number to purchase.

        Returns:
            The JSON response from the Twilio IncomingPhoneNumbers API.

        """
        del authorization, country
        async with httpx.AsyncClient(timeout=20) as client:
            url = f"{self.base_url}/IncomingPhoneNumbers.json"
            try:
                resp = await client.post(
                    url,
                    data={"PhoneNumber": phone_number},
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if resp.status_code >= 300:
                    return classify_number_purchase_status(resp.status_code)
                data = decode_number_purchase_response(resp)
                if data is None:
                    return OutboundSendUnknown(
                        failure_code="number_purchase_response_invalid",
                        status_code=resp.status_code,
                    )
                return number_purchase_success(
                    requested_number=phone_number,
                    response_data=data,
                    status_code=resp.status_code,
                    reference_keys=frozenset({"sid"}),
                )
            except httpx.RequestError:
                return number_purchase_transport_unknown("Twilio")
