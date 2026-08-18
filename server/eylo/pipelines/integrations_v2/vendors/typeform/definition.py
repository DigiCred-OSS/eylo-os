"""Typeform vendor identity."""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, VendorOAuthConfig
from ...registry import registry

FORMS_READ = "forms:read"
RESPONSES_READ = "responses:read"

OAUTH_SCOPES: tuple[str, ...] = (FORMS_READ, RESPONSES_READ)

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="typeform",
        display_name="Typeform",
        description=(
            "Forms and their responses. Curated tools list forms and return "
            "each submission as question-and-answer pairs, rather than the "
            "typed answer envelopes keyed by field id that the API returns."
        ),
        auth_kinds=(VendorAuthKind.OAUTH2, VendorAuthKind.API_KEY),
        base_url="https://api.typeform.com",
        oauth=VendorOAuthConfig(
            authorization_url="https://api.typeform.com/oauth/authorize",
            token_url="https://api.typeform.com/oauth/token",
            scopes=OAUTH_SCOPES,
        ),
        categories=("forms", "productivity"),
        homepage_url="https://www.typeform.com",
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="Authorization",
            value_prefix="Bearer ",
        ),
    )
)

__all__ = ["FORMS_READ", "OAUTH_SCOPES", "RESPONSES_READ", "vendor"]
