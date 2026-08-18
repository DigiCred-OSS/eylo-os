"""Phone-number parsing and normalization contracts."""

from typing import Optional

import phonenumbers
from phonenumbers import NumberParseException
from pydantic import BaseModel


class ParseResult(BaseModel):
    """Result of attempting to parse a phone number."""

    success: bool
    e164: str | None = None
    country_code: int | None = None
    national_number: int | None = None
    error: str | None = None


class PhoneNumberNormalizationService:
    def parse_to_e164(self, raw: str, country: Optional[str] = None) -> ParseResult:
        """Parse a phone number without guessing its country.

        A leading ``+`` is self-describing. A national-format number requires
        an explicit trusted ISO region from its ingress. The platform must not
        silently assign one organization's contacts to another country.
        """
        if not raw or not raw.strip():
            return ParseResult(success=False, error="Empty input")

        candidate = raw.strip()
        if not candidate.startswith("+") and not country:
            return ParseResult(
                success=False,
                error="A national phone number requires an explicit country.",
            )

        try:
            parsed = phonenumbers.parse(candidate, country)

            # Check validity
            if not phonenumbers.is_valid_number(parsed):
                return ParseResult(success=False, error="Invalid phone number")

            # Format to E.164
            e164 = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )

            return ParseResult(
                success=True,
                e164=e164,
                country_code=parsed.country_code,
                national_number=parsed.national_number,
            )

        except NumberParseException:
            return ParseResult(success=False, error="Invalid phone number")
        except Exception:
            return ParseResult(success=False, error="Phone normalization failed")

    def format_for_exotel(self, e164: str) -> str:
        """Exotel requires a 0-prefix for Indian numbers (098...)
        instead of +91.
        """
        if e164.startswith("+91"):
            return "0" + e164[3:]
        return e164

    def format_for_twilio(self, e164: str) -> str:
        return e164
