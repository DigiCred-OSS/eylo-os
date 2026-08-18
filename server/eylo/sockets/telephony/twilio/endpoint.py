"""Resolve Twilio's operator-trusted API endpoint in one place."""

from urllib.parse import quote, urlparse

from eylo.common.config import settings

_TWILIO_VENDOR_ORIGIN = "https://api.twilio.com"
_TWILIO_API_VERSION = "2010-04-01"


def twilio_api_origin() -> str:
    """Return the fixed vendor origin or an explicit deployment override."""
    configured = settings.TWILIO_API_BASE_URL
    if configured is None:
        return _TWILIO_VENDOR_ORIGIN
    value = configured.strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "TWILIO_API_BASE_URL must be an HTTP(S) base URL without "
            "credentials, query, or fragment."
        )
    return value


def twilio_account_url(account_sid: str) -> str:
    """Build one account-scoped Twilio REST URL prefix."""
    encoded_account = quote(account_sid, safe="")
    return (
        f"{twilio_api_origin()}/{_TWILIO_API_VERSION}/Accounts/"
        f"{encoded_account}"
    )


__all__ = ["twilio_account_url", "twilio_api_origin"]
