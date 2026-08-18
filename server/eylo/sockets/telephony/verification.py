"""Read-only carrier credential verification through explicit settings."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from eylo.sockets.telephony.factory import TelephonyFactory
from eylo.sockets.telephony.twilio.endpoint import twilio_account_url


class TelephonyCredentialProbeError(Exception):
    """Raised when carrier construction or read-only authentication fails."""


@dataclass(frozen=True)
class TelephonyCredentialProbeResult:
    provider: str
    account_reference: str


class TelephonyCredentialProbe:
    """Construct the live carrier service, then execute one read-only API call."""

    def __init__(
        self,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._client_factory = client_factory

    async def verify(
        self,
        *,
        provider: str,
        settings: Mapping[str, object],
        timeout_seconds: float,
    ) -> TelephonyCredentialProbeResult:
        service = TelephonyFactory(
            provider=provider,  # type: ignore[arg-type]
            telephony_config=settings,
        ).service
        _require_constructed_provider(service, provider)
        request = _request(provider, settings)
        try:
            async with self._client_factory(
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.send(request)
            response.raise_for_status()
            payload = response.json()
            account_reference = _account_reference(provider, settings, payload)
        except Exception as error:
            raise TelephonyCredentialProbeError(
                "Telephony credential verification failed."
            ) from error
        return TelephonyCredentialProbeResult(
            provider=provider,
            account_reference=account_reference,
        )


def _request(provider: str, settings: Mapping[str, object]) -> httpx.Request:
    if provider == "twilio":
        account_sid = _setting(settings, "account_sid")
        return httpx.Request(
            "GET",
            f"{twilio_account_url(account_sid)}.json",
            headers={
                "Authorization": _basic(account_sid, _setting(settings, "auth_token"))
            },
        )
    if provider == "plivo":
        auth_id = _setting(settings, "auth_id")
        return httpx.Request(
            "GET",
            f"https://api.plivo.com/v1/Account/{auth_id}/",
            headers={
                "Authorization": _basic(auth_id, _setting(settings, "auth_token"))
            },
        )
    if provider == "vonage":
        return httpx.Request(
            "GET",
            "https://rest.nexmo.com/account/get-balance",
            headers={
                "Authorization": _basic(
                    _setting(settings, "api_key"),
                    _setting(settings, "api_secret"),
                )
            },
        )
    if provider == "exotel":
        account_sid = _setting(settings, "account_sid")
        api_host = _setting(settings, "api_host")
        return httpx.Request(
            "GET",
            f"https://{api_host}/v1/Accounts/{account_sid}/Calls.json",
            params={"PageSize": 1},
            headers={
                "Authorization": _basic(
                    _setting(settings, "api_key"),
                    _setting(settings, "api_token"),
                )
            },
        )
    raise TelephonyCredentialProbeError("Unsupported telephony provider.")


def _account_reference(
    provider: str,
    settings: Mapping[str, object],
    payload: Any,
) -> str:
    if not isinstance(payload, Mapping):
        raise TelephonyCredentialProbeError("Carrier returned an invalid response.")
    if provider == "twilio":
        expected = _setting(settings, "account_sid")
        if payload.get("sid") != expected:
            raise TelephonyCredentialProbeError("Twilio account identity mismatch.")
        return expected
    if provider == "plivo":
        expected = _setting(settings, "auth_id")
        if payload.get("auth_id") != expected:
            raise TelephonyCredentialProbeError("Plivo account identity mismatch.")
        return expected
    if provider == "vonage":
        value = payload.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TelephonyCredentialProbeError("Vonage account response is invalid.")
        return _setting(settings, "api_key")
    if provider == "exotel":
        if not ({"Calls", "Metadata"} & set(payload)):
            raise TelephonyCredentialProbeError("Exotel account response is invalid.")
        return _setting(settings, "account_sid")
    raise TelephonyCredentialProbeError("Unsupported telephony provider.")


def _require_constructed_provider(service: object, provider: str) -> None:
    value = getattr(getattr(service, "provider", None), "value", None)
    if value != provider:
        raise TelephonyCredentialProbeError("Carrier adapter construction failed.")
    if provider in {"plivo", "vonage"} and getattr(service, "client", None) is None:
        raise TelephonyCredentialProbeError("Carrier client construction failed.")


def _setting(settings: Mapping[str, object], name: str) -> str:
    value = settings.get(name)
    if not isinstance(value, str) or not value:
        raise TelephonyCredentialProbeError(f"Missing telephony setting: {name}.")
    return value


def _basic(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"
