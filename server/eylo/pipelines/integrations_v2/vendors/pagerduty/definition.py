"""PagerDuty vendor identity.

This vendor is read-only, and the reason is a concrete gap rather than a
preference. Every PagerDuty write — acknowledging, resolving, reassigning —
requires a `From` header naming the acting user's email. That value is per
*installation*, not per vendor, and `static_headers` is deliberately
vendor-level: it carries facts that are true of the API itself, and letting an
operator inject arbitrary headers is a different and larger decision.

Reads need no such header, and "what is on fire, and who is holding the pager"
is most of what an agent is asked anyway.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="pagerduty",
        display_name="PagerDuty",
        description=(
            "Incidents and on-call schedules, read-only. Curated tools report "
            "what is currently firing, who is on call for a service right now, "
            "and the notes people have left on an incident."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        base_url="https://api.pagerduty.com",
        categories=("operations", "monitoring"),
        homepage_url="https://www.pagerduty.com",
        # PagerDuty's REST keys use their own scheme word, not Bearer.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Token token=",
        ),
    )
)

__all__ = ["vendor"]
