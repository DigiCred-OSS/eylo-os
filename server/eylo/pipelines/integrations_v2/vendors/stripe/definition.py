"""Stripe vendor identity.

This vendor is deliberately read-only. Stripe's API accepts only
`application/x-www-form-urlencoded` request bodies, and the curated transport
sends JSON — so writes cannot be expressed here without changing how every
vendor frames a body. Reads are unaffected: they carry no body and Stripe
answers in JSON.

That limit costs less than it sounds. The billing questions an agent is asked —
what did this customer pay, is their subscription active, was that refunded —
are all reads. Taking payments is not something to hand an agent by accident.
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
        vendor="stripe",
        display_name="Stripe",
        description=(
            "Billing history, read-only. Curated tools look a customer up by "
            "email and report their payments, subscriptions, invoices, and "
            "refunds — with amounts converted from Stripe's minor units into "
            "real money and timestamps into readable dates."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        base_url="https://api.stripe.com/v1",
        categories=("billing", "support"),
        homepage_url="https://stripe.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["vendor"]
