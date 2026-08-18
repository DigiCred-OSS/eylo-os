"""Confluence vendor identity.

Like Jira, Confluence Cloud lives at the customer's own
`https://<site>.atlassian.net`, so this vendor declares an instance URL rather
than a fixed origin. An Atlassian "API token" is the password half of HTTP
Basic paired with the account email, so the auth kind is `BASIC`.

The path suffix is `/wiki` rather than `/wiki/api/v2` because Confluence still
splits across two APIs: pages and spaces are v2 (`/wiki/api/v2/...`) while CQL
search only exists on v1 (`/wiki/rest/api/search`). Pinning at `/wiki` keeps
both reachable under one origin policy.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import (
    CuratedVendorSpec,
    InstanceUrlRequirement,
    VendorOAuthConfig,
)
from ...registry import registry

# Atlassian's own OAuth scope names.
READ_CONTENT = "read:content:confluence"
WRITE_CONTENT = "write:content:confluence"
READ_SPACE = "read:space:confluence"

OAUTH_SCOPES: tuple[str, ...] = (READ_CONTENT, WRITE_CONTENT, READ_SPACE)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="confluence",
        display_name="Confluence",
        description=(
            "Team documentation and knowledge base. Curated tools cover "
            "searching, reading, creating, and editing pages."
        ),
        auth_kinds=(VendorAuthKind.BASIC, VendorAuthKind.OAUTH2),
        oauth=VendorOAuthConfig(
            authorization_url="https://auth.atlassian.com/authorize",
            token_url="https://auth.atlassian.com/oauth/token",
            scopes=OAUTH_SCOPES,
            authorization_params=(
                ("audience", "api.atlassian.com"),
                ("prompt", "consent"),
            ),
        ),
        instance_url=InstanceUrlRequirement(
            label="Confluence site URL",
            placeholder="https://your-team.atlassian.net",
            description=(
                "Your Confluence Cloud site. Requests are sent under "
                "<site>/wiki and may not leave this origin."
            ),
            path_suffix="/wiki",
        ),
        categories=("productivity", "documentation"),
        homepage_url="https://www.atlassian.com/software/confluence",
    )
)

__all__ = [
    "OAUTH_SCOPES",
    "READ_CONTENT",
    "READ_SPACE",
    "WRITE_CONTENT",
    "vendor",
]
