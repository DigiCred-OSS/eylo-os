"""Gmail vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# Google's own scope URLs. `modify` subsumes reading, labelling, and trashing;
# `compose` covers drafts and `send` covers delivery. Deliberately absent is
# `https://mail.google.com/`, the only scope that permits permanent deletion.
GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_COMPOSE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"

OAUTH_SCOPES: tuple[str, ...] = (GMAIL_MODIFY, GMAIL_COMPOSE, GMAIL_SEND)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="gmail",
        display_name="Gmail",
        description=(
            "Mail. Curated tools cover searching, reading whole conversations, "
            "sending and replying in thread, drafting, and filing messages by "
            "label. Message bodies arrive already decoded, and replies keep "
            "their threading headers without the agent constructing them."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://gmail.googleapis.com/gmail/v1",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            # Google issues a refresh token only when both are present.
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "communication"),
        homepage_url="https://mail.google.com",
    )
)

__all__ = [
    "GMAIL_COMPOSE",
    "GMAIL_MODIFY",
    "GMAIL_SEND",
    "OAUTH_SCOPES",
    "vendor",
]
