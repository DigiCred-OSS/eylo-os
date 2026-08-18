"""Shopify vendor identity.

Every store has its own `https://<store>.myshopify.com`, so this vendor
declares an instance URL. The API version is pinned in the path rather than
left to default: Shopify dates its versions and retires them, and an unpinned
call silently changes response shape when the default rolls forward.

Auth is a custom app's Admin API access token, presented in Shopify's own
`X-Shopify-Access-Token` header rather than `Authorization`. That is the first
vendor here to place its credential outside `Authorization`, which is exactly
what `ApiKeyPlacement` exists to express.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, InstanceUrlRequirement
from ...registry import registry

API_VERSION = "2025-01"

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="shopify",
        display_name="Shopify",
        description=(
            "Store orders, customers, and products. Curated tools look a "
            "customer up by email, list what they have ordered, read an order "
            "with its line items and fulfillment state, and check product "
            "stock — the questions a support agent actually gets asked."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        instance_url=InstanceUrlRequirement(
            label="Shopify store URL",
            placeholder="https://your-store.myshopify.com",
            description=(
                "Your store's myshopify.com address. Requests are sent under "
                f"<store>/admin/api/{API_VERSION} and may not leave this "
                "origin. The credential is a custom app's Admin API access "
                "token."
            ),
            path_suffix=f"/admin/api/{API_VERSION}",
        ),
        categories=("commerce", "support"),
        homepage_url="https://www.shopify.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="X-Shopify-Access-Token",
        ),
    )
)

__all__ = ["API_VERSION", "vendor"]
