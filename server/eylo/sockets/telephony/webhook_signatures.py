"""Provider-native status callback signature verification."""

from __future__ import annotations

import time
from collections.abc import Mapping

import jwt
from plivo.utils.signature_v3 import validate_v3_signature
from twilio.request_validator import RequestValidator


def verify_status_callback(
    *,
    provider: str,
    config: Mapping[str, object],
    secrets: Mapping[str, str],
    method: str,
    public_url: str,
    headers: Mapping[str, str],
    params: Mapping[str, object],
) -> bool:
    """Verify a callback using the exact pinned carrier revision."""
    headers_lower = {key.lower(): value for key, value in headers.items()}
    if provider == "twilio":
        return RequestValidator(secrets["auth_token"]).validate(
            public_url,
            dict(params),
            headers_lower.get("x-twilio-signature", ""),
        )
    if provider == "plivo":
        signature = headers_lower.get("x-plivo-signature-v3", "")
        nonce = headers_lower.get("x-plivo-signature-v3-nonce", "")
        if not signature or not nonce:
            return False
        return bool(
            validate_v3_signature(
                method,
                public_url,
                nonce,
                secrets["auth_token"],
                signature,
                dict(params),
            )
        )
    if provider == "vonage":
        return _verify_vonage(config, secrets, headers_lower)
    # Exotel has no documented callback-signature contract in the supported
    # adapter surface. Fail closed until a verifiable provider mechanism exists.
    return False


def _verify_vonage(
    config: Mapping[str, object],
    secrets: Mapping[str, str],
    headers: Mapping[str, str],
) -> bool:
    authorization = headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        return False
    try:
        claims = jwt.decode(
            token,
            secrets["signature_secret"],
            algorithms=["HS256"],
            options={"verify_aud": False, "require": ["iat", "jti"]},
        )
        issued_at = int(claims["iat"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return False
    if abs(int(time.time()) - issued_at) > 300:
        return False
    application_id = claims.get("application_id")
    return application_id in {
        None,
        config["application_id"],
    }
