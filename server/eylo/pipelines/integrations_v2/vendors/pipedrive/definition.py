"""Pipedrive vendor identity.

Pipedrive is the first vendor here whose credential travels in the query string
rather than a header. That path exists in the credential layer precisely for
APIs like this one, and it is bound to the pinned origin the same way a header
credential is — so the token cannot ride along to any other host.
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
        vendor="pipedrive",
        display_name="Pipedrive",
        description=(
            "Sales CRM. Curated tools find a person by email, list and create "
            "deals with their stage and value spelled out, move a deal along "
            "the pipeline by stage name, and log a note against a contact."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        base_url="https://api.pipedrive.com/v1",
        categories=("crm", "sales"),
        homepage_url="https://www.pipedrive.com",
        # Pipedrive reads its token from the query string.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.QUERY,
            name="api_token",
        ),
    )
)

__all__ = ["vendor"]
