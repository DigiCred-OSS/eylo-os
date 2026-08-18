"""Carrier adapters for searching and purchasing phone numbers.

Each client follows the same pattern as TwilioRestClient: async httpx calls
with per-org credentials passed at construction time.
"""

import base64
import logging

import httpx
from fastapi import HTTPException

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendTerminal,
    OutboundSendUnknown,
)
from eylo.sockets.telephony.base import TelephonyOperationProfile
from eylo.sockets.telephony.number_purchase import (
    classify_number_purchase_status,
    decode_number_purchase_response,
    number_purchase_profile,
    number_purchase_success,
    number_purchase_transport_unknown,
)

logger = logging.getLogger(__name__)


def _provider_error(
    provider: str,
    operation: str,
    status_code: int,
) -> HTTPException:
    """Keep provider response content out of logs and user-facing errors."""
    logger.error("%s %s error: status=%d", provider, operation, status_code)
    return HTTPException(
        status_code=min(status_code, 502),
        detail=f"{provider} {operation} failed (status {status_code}). Check provider credentials and account status.",
    )


class PlivoNumberClient:
    """Client for Plivo phone number search and purchase APIs.

    Plivo docs: https://www.plivo.com/docs/phone-numbers/api/phone-number/

    Args:
        auth_id: Plivo Auth ID.
        auth_token: Plivo Auth Token.

    """

    def __init__(self, auth_id: str, auth_token: str) -> None:
        self.auth_id = auth_id
        self.auth_token = auth_token
        self.base_url = f"https://api.plivo.com/v1/Account/{auth_id}"
        auth_str = f"{auth_id}:{auth_token}".encode()
        self._auth_header = f"Basic {base64.b64encode(auth_str).decode()}"

    async def search_available_numbers(
        self,
        country: str,
        number_type: str = "local",
        pattern: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search available phone numbers on Plivo.

        Args:
            country: ISO 3166-1 alpha-2 country code.
            number_type: One of "local", "tollfree", "national".
            pattern: Optional area code or digit pattern.
            limit: Max results (1-20).

        """
        type_map = {"Local": "local", "TollFree": "tollfree", "Mobile": "local"}
        plivo_type = type_map.get(number_type, "local")

        params: dict[str, str | int] = {
            "country_iso": country.upper(),
            "type": plivo_type,
            "limit": min(limit, 20),
        }
        if pattern:
            params["pattern"] = pattern

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/PhoneNumber/",
                    params=params,
                    headers={"Authorization": self._auth_header},
                )
                if resp.status_code >= 300:
                    raise _provider_error("Plivo", "search", resp.status_code)

                data = resp.json()
                return data.get("objects", [])
            except httpx.RequestError:
                logger.warning("Plivo number search transport failed")
                raise HTTPException(502, "Unable to reach Plivo. Please try again.")

    def purchase_profile(self) -> TelephonyOperationProfile:
        return number_purchase_profile("plivo", "https://api.plivo.com")

    async def purchase_number(
        self,
        phone_number: str,
        *,
        authorization: OutboundSendAuthorization,
        country: str | None = None,
    ) -> OutboundSendOutcome:
        """Purchase a phone number on Plivo.

        Args:
            phone_number: E.164 phone number (the '+' prefix is stripped for Plivo).

        """
        del authorization, country
        number = phone_number.lstrip("+")

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/PhoneNumber/{number}/",
                    headers={
                        "Authorization": self._auth_header,
                        "Content-Type": "application/json",
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
                    reference_keys=frozenset({"api_id", "id"}),
                )
            except httpx.RequestError:
                return number_purchase_transport_unknown("Plivo")


class VonageNumberClient:
    """Client for Vonage number search and purchase APIs.

    Uses the REST API with api_key/api_secret authentication.
    Vonage docs: https://developer.vonage.com/en/api/numbers

    Args:
        api_key: Vonage API Key.
        api_secret: Vonage API Secret.

    """

    BASE_URL = "https://rest.nexmo.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    async def search_available_numbers(
        self,
        country: str,
        number_type: str = "mobile",
        pattern: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search available phone numbers on Vonage.

        Args:
            country: ISO 3166-1 alpha-2 country code.
            number_type: One of "mobile", "landline", "landline-toll-free".
            pattern: Optional number pattern.
            limit: Max results.

        """
        type_map = {
            "Local": "landline",
            "TollFree": "landline-toll-free",
            "Mobile": "mobile",
        }
        vonage_type = type_map.get(number_type, "mobile")

        params: dict[str, str | int] = {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "country": country.upper(),
            "type": vonage_type,
            "features": "VOICE",
            "size": min(limit, 100),
        }
        if pattern:
            params["pattern"] = pattern
            params["search_pattern"] = 1  # "contains"

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/number/search",
                    params=params,
                )
                if resp.status_code >= 300:
                    raise _provider_error("Vonage", "search", resp.status_code)

                data = resp.json()
                return data.get("numbers", [])
            except httpx.RequestError:
                logger.warning("Vonage number search transport failed")
                raise HTTPException(502, "Unable to reach Vonage. Please try again.")

    def purchase_profile(self) -> TelephonyOperationProfile:
        return number_purchase_profile("vonage", "https://rest.nexmo.com")

    async def purchase_number(
        self,
        phone_number: str,
        *,
        authorization: OutboundSendAuthorization,
        country: str | None = None,
    ) -> OutboundSendOutcome:
        """Purchase a phone number on Vonage.

        Args:
            phone_number: The MSISDN (number without +).
            country: ISO 3166-1 alpha-2 country code.

        """
        del authorization
        if country is None:
            return OutboundSendTerminal(failure_code="number_purchase_country_required")
        msisdn = phone_number.lstrip("+")

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/number/buy",
                    data={
                        "api_key": self.api_key,
                        "api_secret": self.api_secret,
                        "country": country.upper(),
                        "msisdn": msisdn,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if resp.status_code >= 300:
                    return classify_number_purchase_status(resp.status_code)
                data = decode_number_purchase_response(resp)
                if data is None:
                    return OutboundSendUnknown(
                        failure_code="number_purchase_response_invalid",
                        status_code=resp.status_code,
                    )
                embedded_code = data.get("error-code")
                if embedded_code is not None and str(embedded_code) not in {
                    "0",
                    "200",
                }:
                    return OutboundSendTerminal(
                        failure_code="number_purchase_rejected",
                        status_code=resp.status_code,
                    )
                return number_purchase_success(
                    requested_number=phone_number,
                    response_data=data,
                    status_code=resp.status_code,
                    reference_keys=frozenset({"transaction_id", "request_id"}),
                )
            except httpx.RequestError:
                return number_purchase_transport_unknown("Vonage")


class ExotelNumberClient:
    """Client for Exotel virtual number search and purchase APIs.

    Uses Basic auth with api_key:api_token against the org's subdomain.
    Exotel docs: https://developer.exotel.com/api/exophones

    Args:
        api_key: Exotel API Key.
        api_token: Exotel API Token.
        account_sid: Exotel Account SID.
        subdomain: API subdomain (default: api.exotel.com).

    """

    def __init__(
        self,
        api_key: str,
        api_token: str,
        account_sid: str,
        subdomain: str = "api.exotel.com",
    ) -> None:
        _ALLOWED_EXOTEL_SUFFIXES = (".exotel.com", ".exotel.in")
        if not any(subdomain.endswith(s) for s in _ALLOWED_EXOTEL_SUFFIXES):
            raise ValueError(f"Invalid Exotel subdomain: {subdomain}")
        self.account_sid = account_sid
        self.base_url = f"https://{subdomain}/v2_beta/Accounts/{account_sid}"
        auth_str = f"{api_key}:{api_token}".encode()
        self._auth_header = f"Basic {base64.b64encode(auth_str).decode()}"

    async def search_available_numbers(
        self,
        country: str,
        number_type: str = "Local",
        region: str | None = None,
        pattern: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search available ExoPhones by country and provider number type.

        Args:
            country: ISO 3166-1 alpha-2 country code.
            number_type: One of "Local", "TollFree", or "Mobile".
            region: Optional carrier region/circle filter.
            pattern: Optional number substring.
            limit: Maximum results returned to the caller.

        """
        type_map = {
            "Local": "Landline",
            "TollFree": "TollFree",
            "Mobile": "Mobile",
        }
        exotel_type = type_map.get(number_type, "Landline")

        params: dict[str, str] = {}
        if region:
            params["InRegion"] = region.upper()
        if pattern:
            params["Contains"] = pattern

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/AvailablePhoneNumbers/"
                    f"{country.upper()}/{exotel_type}",
                    params=params,
                    headers={"Authorization": self._auth_header},
                )
                if resp.status_code >= 300:
                    raise _provider_error("Exotel", "search", resp.status_code)

                numbers = resp.json()
                if not isinstance(numbers, list):
                    raise HTTPException(
                        502,
                        "Exotel returned an invalid available-number response.",
                    )
                return numbers[:limit]
            except httpx.RequestError:
                logger.warning("Exotel number search transport failed")
                raise HTTPException(502, "Unable to reach Exotel. Please try again.")

    def purchase_profile(self) -> TelephonyOperationProfile:
        return number_purchase_profile(
            "exotel",
            f"https://{self.base_url.split('/')[2]}",
        )

    async def purchase_number(
        self,
        phone_number: str,
        *,
        authorization: OutboundSendAuthorization,
        country: str | None = None,
    ) -> OutboundSendOutcome:
        """Purchase one exact available ExoPhone.

        Args:
            phone_number: The available ExoPhone selected by the user.

        """
        del authorization, country
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/IncomingPhoneNumbers",
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
                    reference_keys=frozenset({"sid", "Sid", "id"}),
                )
            except httpx.RequestError:
                return number_purchase_transport_unknown("Exotel")
