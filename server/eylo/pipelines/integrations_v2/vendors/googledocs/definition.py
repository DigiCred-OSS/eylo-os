"""Google Docs vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

DOCUMENTS = "https://www.googleapis.com/auth/documents"

OAUTH_SCOPES: tuple[str, ...] = (DOCUMENTS,)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="googledocs",
        display_name="Google Docs",
        description=(
            "Documents. Curated tools read a document as plain text, create "
            "one with its opening content in a single step, append to the end "
            "without computing indexes, and replace text throughout. Find "
            "documents with the Google Drive tools."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://docs.googleapis.com/v1",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "documents"),
        homepage_url="https://docs.google.com",
    )
)

__all__ = ["DOCUMENTS", "OAUTH_SCOPES", "vendor"]
