"""Calendly vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="calendly",
        display_name="Calendly",
        description=(
            "Scheduling links and booked meetings. Curated tools list the "
            "booking links an account offers, show what is on the calendar, "
            "reveal who booked each meeting, and cancel with a reason."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.calendly.com",
        oauth=VendorOAuthConfig(
            authorization_url="https://auth.calendly.com/oauth/authorize",
            token_url="https://auth.calendly.com/oauth/token",
            # Calendly issues one level of access and its authorize endpoint
            # takes no scope parameter.
            scopes=(),
        ),
        categories=("scheduling", "productivity"),
        homepage_url="https://calendly.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["vendor"]
