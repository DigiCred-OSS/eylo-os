"""Translate a stored connection credential into exact wire placement.

This is the only place a credential value is read. Everything downstream sees
an `OriginBoundHeaders`/`OriginBoundQuery` pair that the egress boundary refuses
to send anywhere but the one origin it was built for, so a curated tool cannot
leak a token by addressing another host.

Credential key names match `modules/connections`, which V2 reuses unchanged.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from eylo.common.http_egress import (
    HttpEgressPolicyError,
    HttpOrigin,
    OriginBoundHeaders,
    OriginBoundQuery,
)
from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)
from eylo.modules.integrations_v2.domain.errors import (
    AuthKindUnsupportedError,
    CredentialUnavailableError,
)

from .contracts import ApiKeyPlacement

_MAX_CREDENTIAL_CHARS = 16_384

ACCESS_TOKEN_KEY = "access_token"
API_KEY_KEY = "api_key"
USERNAME_KEY = "username"
PASSWORD_KEY = "password"


@dataclass(frozen=True, slots=True)
class VendorWireAuth:
    """Credential material already bound to one permitted origin."""

    origin_headers: OriginBoundHeaders | None = field(default=None, repr=False)
    origin_query: OriginBoundQuery | None = field(default=None, repr=False)


def build_vendor_wire_auth(
    *,
    auth_kind: VendorAuthKind,
    credentials: Mapping[str, Any] | None,
    origin: HttpOrigin,
    api_key_placement: ApiKeyPlacement | None = None,
) -> VendorWireAuth:
    """Place one stored credential onto the wire for exactly one origin.

    Fails closed: an auth kind this vendor cannot express, or a credential that
    is absent or malformed, raises rather than silently producing an
    unauthenticated request that the vendor would answer with a confusing 401.
    """
    if auth_kind is VendorAuthKind.NO_AUTH:
        return VendorWireAuth()

    values = credentials or {}
    if not isinstance(values, Mapping):
        raise CredentialUnavailableError(
            "credentials_invalid",
            "Stored vendor credentials are not a mapping.",
        )

    if auth_kind is VendorAuthKind.OAUTH2:
        token = _required(values, ACCESS_TOKEN_KEY)
        return _headers(origin, {"Authorization": f"Bearer {token}"})

    if auth_kind is VendorAuthKind.API_KEY:
        if api_key_placement is None:
            raise AuthKindUnsupportedError(
                "api_key_placement_missing",
                "Vendor does not declare where its API key belongs.",
            )
        api_key = _required(values, API_KEY_KEY)
        value = (
            f"{api_key_placement.value_prefix} {api_key}"
            if api_key_placement.value_prefix
            else api_key
        )
        if api_key_placement.location is CredentialLocation.HEADER:
            return _headers(origin, {api_key_placement.name: value})
        return _query(origin, {api_key_placement.name: value})

    if auth_kind is VendorAuthKind.BASIC:
        username = _required(values, USERNAME_KEY)
        password = _required(values, PASSWORD_KEY)
        if ":" in username:
            raise CredentialUnavailableError(
                "basic_username_invalid",
                "Basic authentication username cannot contain a colon.",
            )
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        return _headers(origin, {"Authorization": f"Basic {encoded}"})

    raise AuthKindUnsupportedError(
        "auth_kind_unsupported",
        "Vendor authentication kind cannot be placed on the wire.",
    )


def _headers(origin: HttpOrigin, values: dict[str, str]) -> VendorWireAuth:
    try:
        return VendorWireAuth(
            origin_headers=OriginBoundHeaders(origin=origin, values=values)
        )
    except HttpEgressPolicyError as error:
        raise CredentialUnavailableError(
            "credentials_invalid",
            "Stored vendor credential cannot be placed in a header.",
        ) from error


def _query(origin: HttpOrigin, values: dict[str, str]) -> VendorWireAuth:
    try:
        return VendorWireAuth(
            origin_query=OriginBoundQuery(origin=origin, values=values)
        )
    except HttpEgressPolicyError as error:
        raise CredentialUnavailableError(
            "credentials_invalid",
            "Stored vendor credential cannot be placed in a query value.",
        ) from error


def _required(values: Mapping[str, Any], name: str) -> str:
    raw = values.get(name)
    if not isinstance(raw, str):
        raise CredentialUnavailableError(
            "credentials_missing",
            "Required vendor credential is unavailable.",
        )
    value = raw.strip()
    if (
        not value
        or len(value) > _MAX_CREDENTIAL_CHARS
        or "\r" in value
        or "\n" in value
    ):
        raise CredentialUnavailableError(
            "credentials_missing",
            "Required vendor credential is unavailable.",
        )
    return value


__all__ = [
    "ACCESS_TOKEN_KEY",
    "API_KEY_KEY",
    "PASSWORD_KEY",
    "USERNAME_KEY",
    "VendorWireAuth",
    "build_vendor_wire_auth",
]
