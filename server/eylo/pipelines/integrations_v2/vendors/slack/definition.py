"""Slack vendor identity and Web API response handling."""

from __future__ import annotations

from typing import Any

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import (
    CuratedVendorSpec,
    VendorOAuthConfig,
    VendorToolContext,
    VendorToolError,
)
from ...registry import registry

# Slack's own scope names. Bot scopes, not user scopes.
CHANNELS_READ = "channels:read"
CHANNELS_HISTORY = "channels:history"
CHAT_WRITE = "chat:write"
USERS_READ = "users:read"
USERS_READ_EMAIL = "users:read.email"

OAUTH_SCOPES: tuple[str, ...] = (
    CHANNELS_READ,
    CHANNELS_HISTORY,
    CHAT_WRITE,
    USERS_READ,
    USERS_READ_EMAIL,
)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="slack",
        display_name="Slack",
        description=(
            "Team messaging. Curated tools cover posting messages, reading "
            "channel history, and looking people up by email."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://slack.com/api",
        oauth=VendorOAuthConfig(
            authorization_url="https://slack.com/oauth/v2/authorize",
            token_url="https://slack.com/api/oauth.v2.access",
            scopes=OAUTH_SCOPES,
            scope_delimiter=",",
        ),
        categories=("communication",),
        homepage_url="https://slack.com",
    )
)


async def call(
    ctx: VendorToolContext,
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    mutating: bool = False,
) -> dict[str, Any]:
    """Call one Slack Web API method and unwrap its envelope.

    Slack answers a failed call with HTTP 200 and `{"ok": false, "error": ...}`,
    so success has to be read from the body. Every curated Slack tool goes
    through here rather than each rediscovering that.
    """
    send = ctx.mutate if mutating else ctx.read
    response = await send(f"/{method}", method="POST", json=payload or {})
    body = response.data
    if not isinstance(body, dict):
        raise VendorToolError(
            "vendor_response_invalid",
            "Slack returned a non-object response.",
        )
    if not body.get("ok"):
        raise VendorToolError(
            "vendor_rejected",
            f"Slack rejected {method}: {body.get('error', 'unknown_error')}",
        )
    return body


__all__ = [
    "CHANNELS_HISTORY",
    "CHANNELS_READ",
    "CHAT_WRITE",
    "OAUTH_SCOPES",
    "USERS_READ",
    "USERS_READ_EMAIL",
    "call",
    "vendor",
]
