"""Authenticated organization routes for curated vendor browse and install."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user

from ..constants import APP_TAG, OAUTH_ROUTE_PREFIX
from ..controllers import CuratedIntegrationController
from ..schemas.api import (
    AuthorizationRedirectSchema,
    BeginAuthorizationRequestSchema,
    ConnectCredentialRequestSchema,
    ConnectionAggregateSchema,
    ConnectionSchema,
    CuratedVendorDetailSchema,
    CuratedVendorSummarySchema,
    GrantCuratedToolRequestSchema,
    InstallVendorRequestSchema,
    InstallationSchema,
    InstalledToolSchema,
    ReplaceCuratedToolGrantsRequestSchema,
    SetExecutionModeRequestSchema,
)

router = APIRouter(prefix="/{organization_id}", tags=[APP_TAG])

# Public, unauthenticated, and deliberately outside the organization prefix.
# The person completing an authorization is an end user who approved access at
# the provider: they have no console session and no organization in the URL, so
# the state token is the only thing that identifies the flow.
public_router = APIRouter(prefix=OAUTH_ROUTE_PREFIX, tags=[APP_TAG])


@public_router.get("/callback", response_class=HTMLResponse)
async def complete_curated_authorization(
    code: str | None = Query(default=None),
    state: str = Query(min_length=1),
    error: str | None = Query(default=None),
):
    """Handle the provider redirect and store the resulting connection."""
    return await CuratedIntegrationController().complete_public_authorization(
        code=code, state=state, error=error
    )


@router.get(
    "/curated-vendors",
    response_model=list[CuratedVendorSummarySchema],
)
async def list_curated_vendors(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Browse the curated vendors this deployment carries."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_vendors(
        organization_id=organization_id,
    )


@router.get(
    "/curated-vendors/{vendor}",
    response_model=CuratedVendorDetailSchema,
)
async def get_curated_vendor(
    organization_id: UUID,
    vendor: str,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """One curated vendor and the tools it offers."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().get_vendor(
        organization_id=organization_id,
        vendor=vendor,
    )


@router.post(
    "/curated-vendors/{vendor}/install",
    response_model=InstallationSchema,
    status_code=status.HTTP_201_CREATED,
)
async def install_curated_vendor(
    organization_id: UUID,
    vendor: str,
    payload: InstallVendorRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Install one curated vendor for this organization."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().install_vendor(
        organization_id=organization_id,
        vendor=vendor,
        auth_kind=payload.auth_kind,
        actor_id=current_user.member_id,
        instance_url=payload.instance_url,
        oauth_client_id=payload.oauth_client_id,
        oauth_client_secret=payload.oauth_client_secret,
        oauth_tenant=payload.oauth_tenant,
    )


@router.get(
    "/curated-integrations",
    response_model=list[InstallationSchema],
)
async def list_curated_installations(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Curated vendors this organization has installed."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_installations(
        organization_id=organization_id,
    )


@router.get(
    "/aggregate/curated-connections",
    response_model=list[ConnectionAggregateSchema],
)
async def list_curated_connection_aggregates(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Connections plus resolved owners for operator-facing collection views."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_connection_aggregates(
        organization_id=organization_id,
    )


@router.get(
    "/curated-connections",
    response_model=list[ConnectionSchema],
)
async def list_curated_connections(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Connections that authorize curated vendors. Credentials are never returned."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_connections(
        organization_id=organization_id,
    )


@router.delete(
    "/curated-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_curated_connection(
    organization_id: UUID,
    connection_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Clear and remove one curated connection from this organization."""
    _require_organization(current_user, organization_id)
    await CuratedIntegrationController().delete_connection(
        organization_id=organization_id,
        connection_id=connection_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/curated-vendors/{vendor}/tools",
    response_model=list[InstalledToolSchema],
)
async def list_curated_vendor_tools(
    organization_id: UUID,
    vendor: str,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Curated tools for one installed vendor, with their live policy."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_vendor_tools(
        organization_id=organization_id,
        vendor=vendor,
    )


@router.put(
    "/curated-vendors/{vendor}/tools/{tool_name}/execution-mode",
    response_model=InstalledToolSchema,
)
async def set_curated_tool_execution_mode(
    organization_id: UUID,
    vendor: str,
    tool_name: str,
    payload: SetExecutionModeRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Set operator policy for one curated tool.

    Policy is read live at execution, so a change here takes effect on the next
    call rather than when an agent is next rebound.
    """
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().set_execution_mode(
        organization_id=organization_id,
        vendor=vendor,
        tool_name=tool_name,
        execution_mode=payload.execution_mode,
    )


@router.post(
    "/curated-vendors/{vendor}/connect",
    response_model=ConnectionSchema,
    status_code=status.HTTP_201_CREATED,
)
async def connect_curated_vendor(
    organization_id: UUID,
    vendor: str,
    payload: ConnectCredentialRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Store a directly-entered credential for an api_key or basic vendor."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().connect_with_credential(
        organization_id=organization_id,
        vendor=vendor,
        api_key=payload.api_key,
        username=payload.username,
        password=payload.password,
        contact_id=payload.contact_id,
    )


@router.post(
    "/curated-vendors/{vendor}/authorize",
    response_model=AuthorizationRedirectSchema,
)
async def begin_curated_authorization(
    organization_id: UUID,
    vendor: str,
    payload: BeginAuthorizationRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Begin an OAuth flow and return the provider consent URL."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().begin_authorization(
        organization_id=organization_id,
        vendor=vendor,
        contact_id=payload.contact_id,
    )


@router.get(
    "/agents/{agent_id}/curated-tools",
    response_model=list[InstalledToolSchema],
)
async def list_agent_curated_tools(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List curated tools granted to an Agent draft."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().list_agent_tools(
        organization_id=organization_id,
        agent_id=agent_id,
    )


@router.put(
    "/agents/{agent_id}/curated-tools",
    response_model=list[InstalledToolSchema],
)
async def replace_agent_curated_tools(
    organization_id: UUID,
    agent_id: UUID,
    payload: ReplaceCuratedToolGrantsRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Replace the exact curated-tool selection on an Agent draft."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().replace_agent_tools(
        organization_id=organization_id,
        agent_id=agent_id,
        tool_ids=payload.tool_ids,
        expected_draft_version=payload.expected_draft_version,
    )


@router.post(
    "/agents/{agent_id}/curated-tools/{vendor}/{tool_name}",
    response_model=InstalledToolSchema,
)
async def grant_agent_curated_tool(
    organization_id: UUID,
    agent_id: UUID,
    vendor: str,
    tool_name: str,
    payload: GrantCuratedToolRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Grant one installed curated tool to an Agent draft."""
    _require_organization(current_user, organization_id)
    return await CuratedIntegrationController().grant_tool_to_agent(
        organization_id=organization_id,
        agent_id=agent_id,
        vendor=vendor,
        tool_name=tool_name,
        expected_draft_version=payload.expected_draft_version,
    )


@router.delete(
    "/agents/{agent_id}/curated-tools/{vendor}/{tool_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_agent_curated_tool(
    organization_id: UUID,
    agent_id: UUID,
    vendor: str,
    tool_name: str,
    expected_draft_version: int = Query(gt=0),
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Remove one curated tool from an Agent draft."""
    _require_organization(current_user, organization_id)
    await CuratedIntegrationController().revoke_tool_from_agent(
        organization_id=organization_id,
        agent_id=agent_id,
        vendor=vendor,
        tool_name=tool_name,
        expected_draft_version=expected_draft_version,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _require_organization(
    current_user: CurrentUserSchema,
    organization_id: UUID,
) -> None:
    if current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


from .widget import widget_router  # noqa: E402

__all__ = ["public_router", "router", "widget_router"]
