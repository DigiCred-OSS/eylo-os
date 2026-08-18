"""Zendesk adapter for the `integrations_v2` pipeline."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, InstanceUrlRequirement
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="zendesk",
        display_name="Zendesk",
        description=(
            "Customer support tickets. Curated tools search tickets without "
            "Zendesk's query syntax, read a ticket with its whole "
            "conversation, reply publicly or leave an internal note, and move "
            "a ticket through status, priority, and assignment."
        ),
        auth_kinds=(VendorAuthKind.BASIC,),
        instance_url=InstanceUrlRequirement(
            label="Zendesk subdomain URL",
            placeholder="https://your-company.zendesk.com",
            description=(
                "Your Zendesk Support site. Requests are sent under "
                "<site>/api/v2 and may not leave this origin. Sign in with "
                "your agent email followed by /token as the username, and the "
                "API token as the password."
            ),
            path_suffix="/api/v2",
        ),
        categories=("support", "communication"),
        homepage_url="https://www.zendesk.com",
    )
)

__all__ = ["vendor"]
