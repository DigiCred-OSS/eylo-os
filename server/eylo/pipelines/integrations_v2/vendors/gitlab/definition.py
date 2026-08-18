"""GitLab vendor identity.

GitLab is declared with an instance URL rather than a fixed origin, because
`gitlab.com` is only one of its deployments — self-hosted GitLab is common in
exactly the organizations that self-host this platform. An install supplies
whichever it uses, and the egress policy pins requests to it.
"""

from __future__ import annotations

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    VendorAuthKind,
)

from ...contracts import ApiKeyPlacement, CuratedVendorSpec, InstanceUrlRequirement
from ...registry import registry

vendor = registry.register_vendor(
    CuratedVendorSpec(
        vendor="gitlab",
        display_name="GitLab",
        description=(
            "Projects, issues, and merge requests, on gitlab.com or a "
            "self-hosted instance. Curated tools address projects by their "
            "group/name path, and read an issue or merge request together "
            "with its discussion."
        ),
        auth_kinds=(VendorAuthKind.API_KEY,),
        instance_url=InstanceUrlRequirement(
            label="GitLab URL",
            placeholder="https://gitlab.com",
            description=(
                "https://gitlab.com, or your self-hosted GitLab. Requests are "
                "sent under <site>/api/v4 and may not leave this origin."
            ),
            path_suffix="/api/v4",
        ),
        categories=("developer_tools", "productivity"),
        homepage_url="https://gitlab.com",
        # GitLab takes a personal access token in its own header, not in
        # Authorization.
        api_key_placement=ApiKeyPlacement(
            location=CredentialLocation.HEADER,
            name="PRIVATE-TOKEN",
        ),
    )
)

__all__ = ["vendor"]
