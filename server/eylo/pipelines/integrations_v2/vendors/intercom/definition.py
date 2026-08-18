"""Intercom vendor identity.

Intercom versions its API by header. Pinning `Intercom-Version` means an
account whose workspace default moves forward does not silently change the
response shape these tools parse.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

API_VERSION = "2.11"

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="intercom",
        display_name="Intercom",
        description=(
            "Customer messaging and support conversations. Curated tools find "
            "a contact by email, search and read conversations with their "
            "whole message history, reply to a customer, and leave an internal "
            "note."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.intercom.io",
        oauth=VendorOAuthConfig(
            authorization_url="https://app.intercom.com/oauth",
            token_url="https://api.intercom.io/auth/eagle/token",
            # Intercom grants permissions per app rather than per scope, and
            # its authorize endpoint takes no scope parameter.
            scopes=(),
        ),
        categories=("support", "communication"),
        homepage_url="https://www.intercom.com",
        # An access token is presented as a bearer token, the same way an
        # OAuth token is.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
        static_headers=(("Intercom-Version", API_VERSION),),
    )
)

__all__ = ["API_VERSION", "vendor"]
