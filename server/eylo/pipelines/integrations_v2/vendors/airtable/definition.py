"""Airtable vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="airtable",
        display_name="Airtable",
        description=(
            "Bases, tables, and records. Curated tools list what a token can "
            "reach, read records as plain values rather than Airtable's field "
            "envelopes, and filter without writing Airtable's formula "
            "language."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        base_url="https://api.airtable.com/v0",
        categories=("productivity", "data"),
        homepage_url="https://airtable.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["vendor"]
