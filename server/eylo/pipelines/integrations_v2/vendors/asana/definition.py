"""Asana vendor identity.

Auth is a personal access token. Asana also offers OAuth, but its modern
granular scopes (`tasks:read` and friends) coexist with an older no-scope full
access mode, and which one an app gets depends on when it was registered.
Declaring one of those as though it were the truth for every install would be a
guess, so only the token path ships until someone needs the other.
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
        vendor="asana",
        display_name="Asana",
        description=(
            "Projects and tasks. Curated tools find tasks without knowing "
            "Asana's numeric ids, read a task with its comment history, and "
            "create, assign, and complete work using project names and email "
            "addresses."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        base_url="https://app.asana.com/api/1.0",
        categories=("productivity", "project_management"),
        homepage_url="https://asana.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["vendor"]
