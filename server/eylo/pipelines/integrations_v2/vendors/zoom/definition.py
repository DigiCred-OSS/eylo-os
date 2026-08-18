"""Zoom vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# Zoom's own scope names.
MEETING_READ = "meeting:read"
MEETING_WRITE = "meeting:write"
USER_READ = "user:read"

OAUTH_SCOPES: tuple[str, ...] = (MEETING_READ, MEETING_WRITE, USER_READ)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="zoom",
        display_name="Zoom",
        description=(
            "Meetings. Curated tools schedule a meeting and hand back the join "
            "link, list what is coming up, and cancel. Durations are given in "
            "minutes and times in plain ISO 8601."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://api.zoom.us/v2",
        oauth=VendorOAuthConfig(
            authorization_url="https://zoom.us/oauth/authorize",
            token_url="https://zoom.us/oauth/token",
            scopes=OAUTH_SCOPES,
        ),
        categories=("communication", "scheduling"),
        homepage_url="https://zoom.us",
    )
)

__all__ = ["MEETING_READ", "MEETING_WRITE", "OAUTH_SCOPES", "USER_READ", "vendor"]
