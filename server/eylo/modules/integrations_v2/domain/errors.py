"""Domain errors for curated vendor integrations.

Every failure that a caller may reasonably branch on gets a type and a code.
Nothing here raises a bare `ValueError`, so transport can map a failure to a
response without matching on message text.
"""

from __future__ import annotations

import re

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.-]*$")


class IntegrationsV2Error(Exception):
    """Base for every curated-integration domain failure."""

    def __init__(self, code: str, message: str) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError("Integration error code must be an identifier.")
        self.code = code
        super().__init__(message)


class VendorNotFoundError(IntegrationsV2Error):
    """The requested vendor is absent from the running registry."""


class ToolBindingUnavailableError(IntegrationsV2Error):
    """A persisted tool binding names a callable this deployment does not carry.

    Browse, grant, publish, and execution fail closed rather than offering a
    tool the running registry cannot execute.
    """


class IntegrationAlreadyInstalledError(IntegrationsV2Error):
    """The organization already installed this vendor."""


class CredentialUnavailableError(IntegrationsV2Error):
    """No usable credential exists for this organization and vendor.

    Distinct from an unsupported auth kind: this one is fixed by the end user
    authorizing a connection, so callers surface it as `auth_required` rather
    than as a configuration fault.
    """


class AuthKindUnsupportedError(IntegrationsV2Error):
    """The stored auth kind cannot be placed on the wire for this vendor."""


class ToolExecutionBlockedError(IntegrationsV2Error):
    """Operator policy on this exact tool revision forbids execution."""


class ToolApprovalRequiredError(IntegrationsV2Error):
    """Execution requires an approval that has not been granted."""


__all__ = [
    "AuthKindUnsupportedError",
    "CredentialUnavailableError",
    "IntegrationAlreadyInstalledError",
    "IntegrationsV2Error",
    "ToolApprovalRequiredError",
    "ToolBindingUnavailableError",
    "ToolExecutionBlockedError",
    "VendorNotFoundError",
]
