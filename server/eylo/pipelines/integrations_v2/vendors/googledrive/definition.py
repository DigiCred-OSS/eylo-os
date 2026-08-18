"""Google Drive vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

DRIVE = "https://www.googleapis.com/auth/drive"

OAUTH_SCOPES: tuple[str, ...] = (DRIVE,)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="googledrive",
        display_name="Google Drive",
        description=(
            "Files and folders. Curated tools cover finding files without "
            "writing Drive query syntax, creating folders, sharing, moving, "
            "and trashing. Document *contents* are read through the Google "
            "Docs and Google Sheets tools, which return structured data."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://www.googleapis.com/drive/v3",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "storage"),
        homepage_url="https://drive.google.com",
    )
)

__all__ = ["DRIVE", "OAUTH_SCOPES", "vendor"]
