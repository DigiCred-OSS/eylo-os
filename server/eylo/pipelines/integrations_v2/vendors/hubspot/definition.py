"""HubSpot vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import VendorAuthKind

from ...contracts import CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

# HubSpot's own scope names.
CONTACTS_READ = "crm.objects.contacts.read"
CONTACTS_WRITE = "crm.objects.contacts.write"
DEALS_READ = "crm.objects.deals.read"
DEALS_WRITE = "crm.objects.deals.write"
COMPANIES_READ = "crm.objects.companies.read"

OAUTH_SCOPES: tuple[str, ...] = (
    CONTACTS_READ,
    CONTACTS_WRITE,
    DEALS_READ,
    DEALS_WRITE,
    COMPANIES_READ,
)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="hubspot",
        display_name="HubSpot",
        description=(
            "CRM contacts and deals. Curated tools find a person by email, "
            "create and update contacts, list deals with their pipeline stage "
            "resolved to a readable name, and log notes against a record."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2,),
        base_url="https://api.hubapi.com",
        oauth=VendorOAuthConfig(
            authorization_url="https://app.hubspot.com/oauth/authorize",
            token_url="https://api.hubapi.com/oauth/v1/token",
            scopes=OAUTH_SCOPES,
        ),
        categories=("crm", "sales"),
        homepage_url="https://www.hubspot.com",
    )
)

__all__ = [
    "COMPANIES_READ",
    "CONTACTS_READ",
    "CONTACTS_WRITE",
    "DEALS_READ",
    "DEALS_WRITE",
    "OAUTH_SCOPES",
    "vendor",
]
