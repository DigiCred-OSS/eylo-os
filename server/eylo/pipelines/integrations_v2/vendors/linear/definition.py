"""Linear vendor identity and connection surface."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry
from .scopes import OAUTH_SCOPES

GRAPHQL_PATH = "/graphql"

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="linear",
        display_name="Linear",
        description=(
            "Issue tracking and project planning for software teams. Curated "
            "tools cover issues, comments, labels, teams, and users."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.linear.app",
        oauth=VendorOAuthConfig(
            authorization_url="https://linear.app/oauth/authorize",
            token_url="https://api.linear.app/oauth/token",
            scopes=OAUTH_SCOPES,
            scope_delimiter=",",
        ),
        categories=("productivity", "developer_tools"),
        homepage_url="https://linear.app",
        # Linear takes a personal API key as the raw Authorization value.
        # A "Bearer " prefix here is rejected by the API.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
        ),
    )
)

__all__ = ["GRAPHQL_PATH", "vendor"]
