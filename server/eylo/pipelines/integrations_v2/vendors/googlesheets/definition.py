"""Google Sheets vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

SPREADSHEETS = "https://www.googleapis.com/auth/spreadsheets"

OAUTH_SCOPES: tuple[str, ...] = (SPREADSHEETS,)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="googlesheets",
        display_name="Google Sheets",
        description=(
            "Spreadsheets. Curated tools read rows as records keyed by the "
            "header row, append a row by naming its columns, update a range, "
            "and create sheets. Find spreadsheets with the Google Drive tools."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://sheets.googleapis.com/v4",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "data"),
        homepage_url="https://sheets.google.com",
    )
)

__all__ = ["OAUTH_SCOPES", "SPREADSHEETS", "vendor"]
