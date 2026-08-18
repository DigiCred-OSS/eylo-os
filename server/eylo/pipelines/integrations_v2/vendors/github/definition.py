"""GitHub vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# GitHub's own scope names.
REPO = "repo"
READ_ORG = "read:org"
READ_USER = "read:user"

OAUTH_SCOPES: tuple[str, ...] = (REPO, READ_ORG, READ_USER)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="github",
        display_name="GitHub",
        description=(
            "Repositories, issues, and pull requests. Curated tools search "
            "issues without GitHub's query syntax, and read an issue or pull "
            "request together with its comments, reviews, and changed files in "
            "one call."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.github.com",
        oauth=VendorOAuthConfig(
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes=OAUTH_SCOPES,
        ),
        categories=("developer_tools", "productivity"),
        homepage_url="https://github.com",
        # A personal access token is presented exactly like an OAuth token.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["OAUTH_SCOPES", "READ_ORG", "READ_USER", "REPO", "vendor"]
