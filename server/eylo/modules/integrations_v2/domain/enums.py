"""Domain vocabulary for curated vendor integrations.

This module owns the words. Pipelines and transport import from here rather
than restating a set of allowed values, so a new auth kind or tool effect has
exactly one place to be added.
"""

from __future__ import annotations

from enum import Enum


class VendorAuthKind(str, Enum):
    """How an organization proves identity to one vendor.

    Only executable auth modes belong here. OAuth1 and OAuth1a are unsupported.
    """

    NO_AUTH = "no_auth"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"


class ToolEffect(str, Enum):
    """Whether one curated tool may change vendor-side state.

    This drives durability, not documentation. A `MUTATION` tool is refused
    execution without a committed `TOOL_USE` owner and a durable context; a
    `READ` tool is executed directly and writes no outbound receipt.
    """

    READ = "read"
    MUTATION = "mutation"


class CredentialLocation(str, Enum):
    """Where a credential value is placed on the wire."""

    HEADER = "header"
    QUERY = "query"


class ToolExecutionMode(str, Enum):
    """Operator policy on one installed tool, enforced before dispatch."""

    AUTO = "auto"
    REQUIRES_APPROVAL = "requires_approval"
    DISABLED = "disabled"


__all__ = [
    "CredentialLocation",
    "ToolEffect",
    "ToolExecutionMode",
    "VendorAuthKind",
]
