"""HTTP routes for the `tools` domain."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.contracts.provider_config import Capability
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.tools.constants import APP_TAG
from eylo.modules.tools.controllers import ToolController
from eylo.modules.tools.schemas.api import (
    ToolCreateRequestSchema,
    ToolListResponseSchema,
    ToolPublishRequestSchema,
    ToolResponseSchema,
    ToolRevisionResponseSchema,
    ToolRevokeRequestSchema,
    ToolUpdateRequestSchema,
)

router = APIRouter(prefix="/{organization_id}/tools", tags=[APP_TAG])


@router.get("/system-catalog", response_model=ToolListResponseSchema)
async def list_system_tools_catalog(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List all available system tools from the code registry.

    Returns virtual tool objects with deterministic UUIDs scoped to the org.
    These can be mapped to agents via the agent-tool assignment API.
    """
    _require_organization(current_user, organization_id)
    return await ToolController().list_system_catalog(organization_id)


@router.get("/provider-catalog", response_model=ToolListResponseSchema)
async def list_provider_tools_catalog(
    organization_id: UUID,
    capability: Capability,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List Agent tools enabled by one provider capability.

    The projection is independent of current configuration readiness so an
    operator can understand what the capability unlocks before configuring it.
    """
    _require_organization(current_user, organization_id)
    return await ToolController().list_provider_catalog(
        organization_id,
        capability,
    )


@router.get("", response_model=ToolListResponseSchema)
async def list_tools(
    organization_id: UUID,
    mcp_server_id: UUID | None = None,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().list_tools(organization_id, mcp_server_id)


@router.post("", response_model=ToolResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_tool(
    organization_id: UUID,
    request: ToolCreateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().create_tool(organization_id, request)


@router.get("/{tool_id}", response_model=ToolResponseSchema)
async def get_tool(
    organization_id: UUID,
    tool_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().get_tool(tool_id, current_user)


@router.put("/{tool_id}", response_model=ToolResponseSchema)
async def update_tool(
    organization_id: UUID,
    tool_id: UUID,
    request: ToolUpdateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().update_tool(tool_id, organization_id, request)


@router.post(
    "/{tool_id}/publish",
    response_model=ToolRevisionResponseSchema,
)
async def publish_tool(
    organization_id: UUID,
    tool_id: UUID,
    request: ToolPublishRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().publish_tool(
        tool_id=tool_id,
        organization_id=organization_id,
        expected_draft_version=request.expected_draft_version,
        actor_id=current_user.member_id,
    )


@router.post("/{tool_id}/withdraw", response_model=ToolResponseSchema)
async def withdraw_tool(
    organization_id: UUID,
    tool_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().withdraw_tool(
        tool_id=tool_id,
        organization_id=organization_id,
    )


@router.post(
    "/{tool_id}/revisions/{revision}/revoke",
    response_model=ToolRevisionResponseSchema,
)
async def revoke_tool(
    organization_id: UUID,
    tool_id: UUID,
    revision: int,
    request: ToolRevokeRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().revoke_tool(
        tool_id=tool_id,
        revision=revision,
        organization_id=organization_id,
        actor_id=current_user.member_id,
        reason=request.reason,
    )


@router.delete("/{tool_id}", status_code=status.HTTP_200_OK)
async def delete_tool(
    organization_id: UUID,
    tool_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _require_organization(current_user, organization_id)
    return await ToolController().delete_tool(tool_id, organization_id)


def _require_organization(
    current_user: CurrentUserSchema,
    organization_id: UUID,
) -> None:
    if current_user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
