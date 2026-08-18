"""Shared safe result contract for charged carrier number purchases."""

import logging
from typing import Protocol

import httpx

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendSucceeded,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.sockets.telephony.base import (
    TelephonyOperationCapabilities,
    TelephonyOperationProfile,
    classify_provider_failure,
)

logger = logging.getLogger(__name__)


class NumberPurchaseClient(Protocol):
    """One exact charged number-purchase adapter."""

    def purchase_profile(self) -> TelephonyOperationProfile: ...

    async def purchase_number(
        self,
        phone_number: str,
        *,
        authorization: OutboundSendAuthorization,
        country: str | None = None,
    ) -> OutboundSendOutcome: ...


class _ProviderStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Provider request failed with status {status_code}.")


def number_purchase_profile(
    provider: str,
    destination_origin: str,
) -> TelephonyOperationProfile:
    return TelephonyOperationProfile(
        provider_operation=f"{provider}.phone_number.purchase",
        transport_kind=OutboundTransportKind.HTTP,
        destination_origin=destination_origin,
        capabilities=TelephonyOperationCapabilities(
            provider_idempotency=False,
            reconciliation=False,
        ),
    )


def classify_number_purchase_status(status_code: int) -> OutboundSendOutcome:
    return classify_provider_failure(
        _ProviderStatusError(status_code),
        operation="number_purchase",
    )


def number_purchase_transport_unknown(provider: str) -> OutboundSendUnknown:
    logger.warning("%s number purchase transport failed", provider)
    return OutboundSendUnknown(failure_code="number_purchase_unconfirmed")


def decode_number_purchase_response(response: httpx.Response) -> dict | None:
    if not response.content:
        return {}
    try:
        value = response.json()
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def number_purchase_success(
    *,
    requested_number: str,
    response_data: dict,
    status_code: int,
    reference_keys: frozenset[str],
) -> OutboundSendOutcome:
    observed = _normalize_phone_number(
        _find_value(
            response_data,
            frozenset({"phone_number", "PhoneNumber", "number", "msisdn"}),
        )
    )
    if observed is not None and observed != requested_number:
        return OutboundSendUnknown(
            failure_code="number_purchase_identity_mismatch",
            status_code=status_code,
        )
    reference = _find_value(response_data, reference_keys)
    if not isinstance(reference, str) or not reference.strip():
        reference = requested_number
    normalized_reference = reference.strip()
    if len(normalized_reference) > 320:
        normalized_reference = requested_number
    return OutboundSendSucceeded(
        provider_reference=normalized_reference,
        status_code=status_code,
    )


def _normalize_phone_number(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized.startswith("+"):
        return normalized
    if normalized.isdigit():
        return f"+{normalized}"
    return None


def _find_value(value: object, keys: frozenset[str]) -> object | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                return item
        for item in value.values():
            found = _find_value(item, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_value(item, keys)
            if found is not None:
                return found
    return None


__all__ = [
    "NumberPurchaseClient",
    "classify_number_purchase_status",
    "decode_number_purchase_response",
    "number_purchase_profile",
    "number_purchase_success",
    "number_purchase_transport_unknown",
]
