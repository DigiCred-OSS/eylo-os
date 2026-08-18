"""Freshdesk vendor identity.

Freshdesk authenticates with HTTP Basic where the API key is the *username* and
the password is any non-empty placeholder — conventionally `X`. That is
unusual enough to be worth stating in the connection surface, because an
operator who puts the key in the password field gets a 401 with no explanation.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, InstanceUrlRequirement
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="freshdesk",
        display_name="Freshdesk",
        description=(
            "Support tickets. Curated tools search and read tickets with their "
            "conversation, open new ones, and — separately and explicitly — "
            "either reply to the customer or leave an internal note."
        ),
        auth_kinds=(VendorAuthKind.BASIC,),
        instance_url=InstanceUrlRequirement(
            label="Freshdesk domain",
            placeholder="https://your-company.freshdesk.com",
            description=(
                "Your Freshdesk site. Requests are sent under <site>/api/v2 "
                "and may not leave this origin. For the credential, put your "
                "API key in the username field and X in the password field."
            ),
            path_suffix="/api/v2",
        ),
        categories=("support", "communication"),
        homepage_url="https://freshdesk.com",
    )
)

__all__ = ["vendor"]
