"""Outlook vendor identity, over Microsoft Graph.

Microsoft's identity endpoints are per-tenant and require PKCE, but neither is
declared here: both belong to the OAuth app an operator configures, not to the
vendor. The authorize and token URLs carry `{tenant}`, substituted from
`auth_config.tenant`, and PKCE is switched on with `auth_config.pkce`. Both are
handled by the curated OAuth pipeline.

Graph itself is a single fixed origin, so this vendor needs no instance URL.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

AUTHORIZATION_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Microsoft's own scope names.
MAIL_READ = "https://graph.microsoft.com/Mail.Read"
MAIL_SEND = "https://graph.microsoft.com/Mail.Send"
OFFLINE_ACCESS = "offline_access"

OAUTH_SCOPES: tuple[str, ...] = (MAIL_READ, MAIL_SEND, OFFLINE_ACCESS)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="outlook",
        display_name="Outlook",
        description=(
            "Microsoft 365 mail. Curated tools cover searching, reading, "
            "sending, and replying to messages."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://graph.microsoft.com/v1.0",
        oauth=VendorOAuthConfig(
            authorization_url=AUTHORIZATION_URL,
            token_url=TOKEN_URL,
            scopes=OAUTH_SCOPES,
            pkce=True,
        ),
        categories=("communication", "productivity"),
        homepage_url="https://outlook.com",
    )
)

__all__ = [
    "AUTHORIZATION_URL",
    "MAIL_READ",
    "MAIL_SEND",
    "OAUTH_SCOPES",
    "OFFLINE_ACCESS",
    "TOKEN_URL",
    "vendor",
]
