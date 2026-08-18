"""Jira vendor identity.

Jira Cloud is the reference case for a customer-owned origin: every
organization reaches it at its own `https://<site>.atlassian.net`, so this
vendor declares an `InstanceUrlRequirement` instead of a fixed `base_url`.

Atlassian's "API token" is not a bearer key — it is the password half of HTTP
Basic, paired with the account email. So the auth kind here is `BASIC`, and the
credential fields are `username` (the email) and `password` (the token).
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
READ_JIRA_WORK = "read:jira-work"
WRITE_JIRA_WORK = "write:jira-work"
READ_JIRA_USER = "read:jira-user"

OAUTH_SCOPES: tuple[str, ...] = (READ_JIRA_WORK, WRITE_JIRA_WORK, READ_JIRA_USER)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="jira",
        display_name="Jira",
        description=(
            "Issue tracking and project management. Curated tools cover "
            "searching, reading, creating, and commenting on issues."
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
            label="Jira site URL",
            placeholder="https://your-team.atlassian.net",
            description=(
                "Your Jira Cloud site. Requests are sent to "
                "<site>/rest/api/3 and may not leave this origin."
            ),
            path_suffix="/rest/api/3",
        ),
        categories=("productivity", "developer_tools"),
        homepage_url="https://www.atlassian.com/software/jira",
    )
)

__all__ = [
    "OAUTH_SCOPES",
    "READ_JIRA_USER",
    "READ_JIRA_WORK",
    "WRITE_JIRA_WORK",
    "vendor",
]
