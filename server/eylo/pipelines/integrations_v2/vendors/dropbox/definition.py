"""Dropbox vendor identity.

`token_access_type=offline` is required for Dropbox to issue a refresh token at
all; without it the connection stops working in four hours and the periodic
refresh job has nothing to work with.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# Dropbox's own scope names.
FILES_READ = "files.metadata.read"
FILES_WRITE = "files.content.write"
SHARING_WRITE = "sharing.write"

OAUTH_SCOPES: tuple[str, ...] = (FILES_READ, FILES_WRITE, SHARING_WRITE)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="dropbox",
        display_name="Dropbox",
        description=(
            "Files and folders. Curated tools search, browse, organise, and "
            "create share links. File contents are not read here — Dropbox "
            "serves those as raw bytes from a separate host."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://api.dropboxapi.com/2",
        oauth=VendorOAuthConfig(
            authorization_url="https://www.dropbox.com/oauth2/authorize",
            token_url="https://api.dropboxapi.com/oauth2/token",
            scopes=OAUTH_SCOPES,
            # Without this Dropbox issues no refresh token at all.
            authorization_params=(("token_access_type", "offline"),),
        ),
        categories=("productivity", "storage"),
        homepage_url="https://www.dropbox.com",
    )
)

__all__ = ["FILES_READ", "FILES_WRITE", "OAUTH_SCOPES", "SHARING_WRITE", "vendor"]
