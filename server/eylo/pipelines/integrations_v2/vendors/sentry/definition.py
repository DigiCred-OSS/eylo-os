"""Sentry vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# Sentry's own scope names.
PROJECT_READ = "project:read"
EVENT_READ = "event:read"
EVENT_WRITE = "event:write"

OAUTH_SCOPES: tuple[str, ...] = (PROJECT_READ, EVENT_READ, EVENT_WRITE)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="sentry",
        display_name="Sentry",
        description=(
            "Error tracking. Curated tools list what is breaking and how "
            "often, read an issue with a real stack frame rather than a raw "
            "event blob, and resolve or mute an issue once it is handled."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://sentry.io/api/0",
        oauth=VendorOAuthConfig(
            authorization_url="https://sentry.io/oauth/authorize/",
            token_url="https://sentry.io/oauth/token/",
            scopes=OAUTH_SCOPES,
        ),
        categories=("developer_tools", "monitoring"),
        homepage_url="https://sentry.io",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["EVENT_READ", "EVENT_WRITE", "OAUTH_SCOPES", "PROJECT_READ", "vendor"]
