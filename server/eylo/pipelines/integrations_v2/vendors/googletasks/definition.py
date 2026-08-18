"""Google Tasks vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

TASKS = "https://www.googleapis.com/auth/tasks"

OAUTH_SCOPES: tuple[str, ...] = (TASKS,)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="googletasks",
        display_name="Google Tasks",
        description=(
            "Task lists. Curated tools list, create, complete, and remove "
            "tasks, addressing lists by name rather than id and accepting "
            "plain due dates."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://tasks.googleapis.com/tasks/v1",
        oauth=VendorOAuthConfig(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES,
            authorization_params=(("access_type", "offline"), ("prompt", "consent")),
        ),
        categories=("productivity", "tasks"),
        homepage_url="https://tasks.google.com",
    )
)

__all__ = ["OAUTH_SCOPES", "TASKS", "vendor"]
