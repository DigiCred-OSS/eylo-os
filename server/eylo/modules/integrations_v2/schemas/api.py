"""Transport shapes for the curated integration surface.

Separate from `indb.py` on purpose: these are camelCase wire contracts an
operator console depends on, and they should be free to differ from what the
service returns internally.

Catalog responses are assembled from the registry rather than from rows. There
is no catalog table to read — the running deployment's code *is* the catalog.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.connections.models import ConnectionStatus
from eylo.modules.mappers.enums import ConnectionKind

from ..domain.enums import ToolEffect, ToolExecutionMode, VendorAuthKind


class CuratedToolCatalogSchema(EyloBaseApiSchema):
    """One curated tool as offered by the catalog, before any org installs it."""

    wire_id: str = Field(description="Stable binding, e.g. linear.list_issues.")
    name: str = Field(
        description="Vendor-scoped tool name, and the path segment used to "
        "address this tool, e.g. list_issues."
    )
    agent_name: str = Field(
        description="Fully qualified name an agent sees, e.g. linear_list_issues."
    )
    display_name: str
    description: str
    effect: ToolEffect = Field(
        description="Whether the tool may change vendor-side state."
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Provider-native scopes this tool needs.",
    )


class CuratedVendorSummarySchema(EyloBaseApiSchema):
    """One curated vendor in the browse list."""

    vendor: str
    display_name: str
    description: str
    categories: list[str] = Field(default_factory=list)
    auth_kinds: list[VendorAuthKind] = Field(default_factory=list)
    homepage_url: str | None = None
    requires_instance_url: bool = Field(
        default=False,
        description="Whether installing requires a customer-owned origin.",
    )
    instance_url_label: str | None = None
    instance_url_placeholder: str | None = None
    requires_oauth_app: bool = Field(
        default=False,
        description="Whether installing requires your own OAuth client id and secret.",
    )
    requires_oauth_tenant: bool = Field(
        default=False,
        description="Whether the provider's endpoints are per-tenant.",
    )
    tool_count: int = Field(description="Curated tools this deployment carries.")
    installed: bool = Field(description="Whether this organization installed it.")


class CuratedVendorDetailSchema(CuratedVendorSummarySchema):
    """One curated vendor with the tools it offers."""

    tools: list[CuratedToolCatalogSchema] = Field(default_factory=list)


class InstallVendorRequestSchema(EyloBaseApiSchema):
    """Install one curated vendor for the authenticated organization."""

    auth_kind: VendorAuthKind = Field(
        description="Which of the vendor's supported auth modes to use."
    )
    instance_url: str | None = Field(
        default=None,
        description="Customer-owned HTTPS origin, for vendors that require one.",
    )
    oauth_client_id: str | None = Field(
        default=None, description="Client id of your own OAuth app for this vendor."
    )
    oauth_client_secret: str | None = Field(
        default=None,
        description="Client secret of your own OAuth app. Stored encrypted.",
    )
    oauth_tenant: str | None = Field(
        default=None,
        description="Directory id, for per-tenant providers such as Microsoft.",
    )


class ConnectCredentialRequestSchema(EyloBaseApiSchema):
    """Direct credential entry, for vendors not using OAuth."""

    api_key: str | None = Field(
        default=None, description="API key, for api_key vendors."
    )
    username: str | None = Field(
        default=None, description="Username or account email, for basic vendors."
    )
    password: str | None = Field(
        default=None, description="Password or API token, for basic vendors."
    )
    contact_id: uuid.UUID | None = Field(
        default=None,
        description="Bind to one end user. Omit for an organization-wide connection.",
    )


class BeginAuthorizationRequestSchema(EyloBaseApiSchema):
    """Start an OAuth flow for an installed vendor."""

    contact_id: uuid.UUID | None = Field(
        default=None,
        description="Bind the resulting connection to one end user.",
    )


class AuthorizationRedirectSchema(EyloBaseApiSchema):
    """Where to send the user to grant access."""

    authorization_url: str
    callback_origin: str = Field(
        description="Trusted origin that will post the OAuth completion message."
    )
    state: str


class ConnectionSchema(EyloBaseApiSchema):
    """A stored authorization. Credentials are never included."""

    id: uuid.UUID
    vendor: str
    display_name: str | None = None
    connection_kind: ConnectionKind
    status: ConnectionStatus
    contact_id: uuid.UUID | None = None
    credentials_expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConnectionOwnerSummarySchema(EyloBaseApiSchema):
    """Human-readable owner projection for an operator-facing connection list."""

    id: uuid.UUID
    kind: ConnectionKind
    display_name: str


class ConnectionAggregateSchema(ConnectionSchema):
    """Connection plus its resolved organization or contact owner."""

    owner: ConnectionOwnerSummarySchema


class InstalledToolSchema(EyloBaseApiSchema):
    """One curated tool an organization has materialized, with its policy."""

    id: uuid.UUID
    wire_id: str
    name: str = Field(description="Path segment used to address this tool.")
    agent_name: str = Field(description="Fully qualified name an agent sees.")
    display_name: str
    description: str
    effect: ToolEffect
    execution_mode: ToolExecutionMode


class InstallationSchema(EyloBaseApiSchema):
    """One organization's installation of a curated vendor."""

    id: uuid.UUID
    vendor: str
    display_name: str
    auth_kind: VendorAuthKind
    instance_url: str | None = None
    oauth_client_id: str | None = None
    oauth_tenant: str | None = None
    installed_at: datetime
    installed_by: uuid.UUID


class SetExecutionModeRequestSchema(EyloBaseApiSchema):
    """Operator policy for one curated tool."""

    execution_mode: ToolExecutionMode


class GrantCuratedToolRequestSchema(EyloBaseApiSchema):
    """Optimistic-concurrency guard for changing an Agent draft grant."""

    expected_draft_version: int = Field(gt=0)


class ReplaceCuratedToolGrantsRequestSchema(EyloBaseApiSchema):
    """Exact curated-tool selection plus its optimistic-concurrency guard."""

    tool_ids: list[uuid.UUID] = Field(max_length=1000)
    expected_draft_version: int = Field(gt=0)


class WidgetConnectCredentialRequestSchema(EyloBaseApiSchema):
    """End-user credential entry; ownership always comes from the widget session."""

    api_key: str | None = None
    username: str | None = None
    password: str | None = None


class WidgetCuratedToolSchema(EyloBaseApiSchema):
    """Safe curated tool metadata shown to an end user."""

    id: uuid.UUID
    name: str
    slug: str
    display_name: str
    description: str
    kind: str = "CURATED"


class WidgetCuratedIntegrationSchema(EyloBaseApiSchema):
    """Installed vendor plus connection state for the current contact."""

    id: uuid.UUID
    name: str
    slug: str
    display_name: str
    description: str
    auth_kind: VendorAuthKind
    connection_kind: str
    has_active_connection: bool
    source: str = "curated"
    vendor: str


class WidgetCuratedToolGroupSchema(EyloBaseApiSchema):
    """Curated tools grouped by the vendor that authorizes them."""

    integration: WidgetCuratedIntegrationSchema
    tools: list[WidgetCuratedToolSchema]


class WidgetCuratedCapabilitiesRequestSchema(EyloBaseApiSchema):
    """Published Agents whose curated capabilities the widget will render."""

    agent_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class WidgetAgentCuratedCapabilitiesSchema(EyloBaseApiSchema):
    """Curated capability groups belonging to one published Agent revision."""

    agent_id: uuid.UUID
    integrations: list[WidgetCuratedToolGroupSchema]


__all__ = [
    "AuthorizationRedirectSchema",
    "BeginAuthorizationRequestSchema",
    "ConnectCredentialRequestSchema",
    "ConnectionAggregateSchema",
    "ConnectionOwnerSummarySchema",
    "ConnectionSchema",
    "CuratedToolCatalogSchema",
    "CuratedVendorDetailSchema",
    "CuratedVendorSummarySchema",
    "GrantCuratedToolRequestSchema",
    "InstallVendorRequestSchema",
    "InstallationSchema",
    "InstalledToolSchema",
    "SetExecutionModeRequestSchema",
    "WidgetConnectCredentialRequestSchema",
    "WidgetAgentCuratedCapabilitiesSchema",
    "WidgetCuratedCapabilitiesRequestSchema",
    "WidgetCuratedIntegrationSchema",
    "WidgetCuratedToolGroupSchema",
    "WidgetCuratedToolSchema",
]
