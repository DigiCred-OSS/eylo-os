"""Google Calendar vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# Google's own scope URLs.
CALENDAR = "https://www.googleapis.com/auth/calendar"
CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"

OAUTH_SCOPES: tuple[str, ...] = (CALENDAR, CALENDAR_EVENTS)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="googlecalendar",
        display_name="Google Calendar",
        description=(
            "Calendars and scheduling. Curated tools cover finding, creating, "
            "moving, and cancelling events, and finding free time across "
            "several calendars at once."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://www.googleapis.com/calendar/v3",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            # Google issues a refresh token only when both are present.
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "scheduling"),
        homepage_url="https://calendar.google.com",
    )
)

__all__ = [
    "CALENDAR",
    "CALENDAR_EVENTS",
    "OAUTH_SCOPES",
    "vendor",
]
