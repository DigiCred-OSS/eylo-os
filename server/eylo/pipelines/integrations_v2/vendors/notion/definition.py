"""Notion vendor identity.

Notion rejects any request without a `Notion-Version` header, and the version
pins the response shape. That makes it vendor knowledge rather than
organization configuration, so it is declared here — pinning it also means a
Notion API revision cannot silently change what these tools parse.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

API_VERSION = "2022-06-28"

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="notion",
        display_name="Notion",
        description=(
            "Workspace pages and databases. Curated tools search the "
            "workspace, read a page's content as text, create and append to "
            "pages, and query databases with plain filters."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.notion.com/v1",
        oauth=VendorOAuthConfig(
            authorization_url="https://api.notion.com/v1/oauth/authorize",
            token_url="https://api.notion.com/v1/oauth/token",
            # Notion has no scope model: capabilities are chosen when the
            # integration is consented to, and its authorize endpoint takes no
            # `scope` parameter at all.
            scopes=(),
            authorization_params=(("owner", "user"),),
        ),
        categories=("productivity", "documentation"),
        homepage_url="https://www.notion.so",
        # An internal integration token is presented as a bearer token.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
        static_headers=(("Notion-Version", API_VERSION),),
    )
)

__all__ = ["API_VERSION", "vendor"]
