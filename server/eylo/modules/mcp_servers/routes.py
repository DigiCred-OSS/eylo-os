"""Operator routes for MCP servers.

Registration and discovery are separate calls because they are separate
decisions. Registering records an address; discovering asks that address what it
can do and writes tools an agent may then be given. An operator should see the
second list before attaching any of it to an agent.

There is no background re-discovery. A server cannot change what its tools claim
to do between an operator reviewing them and an agent running them unless
someone asks it to — which is the only real mitigation available for a server
describing tools to a model.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from eylo.common.database import get_transaction, start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.mcp_servers.service import (
    MCPServerError,
    MCPServerNotFoundError,
    MCPServerService,
    redacted_server,
)
from eylo.modules.tools.schemas.executors.mcp import MCPToolExecutorConfig
from eylo.pipelines.mcp.tools import discover_mcp_server

router = APIRouter(prefix="/{organization_id}/mcp-servers", tags=[APP_TAG])


class MCPServerCreate(BaseModel):
    name: str = Field(..., max_length=128)
    url: str = Field(
        ..., description="Streamable HTTP endpoint. stdio is not supported."
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Sent on every request — this is where a bearer token goes. Values "
            "are never returned."
        ),
    )


class MCPServerPatch(BaseModel):
    expected_draft_version: int = Field(..., gt=0)
    name: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=2048)
    headers: dict[str, str | None] | None = Field(
        default=None,
        description=(
            "Secret patch: omitted keys stay unchanged; string replaces; null removes."
        ),
    )


class MCPServerRevoke(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2_000)


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


@router.get("")
async def list_mcp_servers(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Servers registered for this organization, with header values masked."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        service = MCPServerService(get_transaction())
        return [
            redacted_server(server)
            for server in await service.list_servers(organization_id)
        ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_mcp_server(
    organization_id: UUID,
    request: MCPServerCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Record a server. Does not contact it — see the discover endpoint."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = MCPServerService(get_transaction())
        try:
            server = await service.register(
                organization_id=organization_id,
                name=request.name,
                url=request.url,
                headers=request.headers,
            )
        except MCPServerError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return redacted_server(server)


@router.post("/{server_id}/discover")
async def discover_mcp_tools(
    organization_id: UUID,
    server_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Ask the server what it offers and synchronize immutable tool revisions.

    A changed tool appends a revision. A missing tool is withdrawn from new
    grants without deleting exact historical references. The response is what
    an operator reviews before attaching any of it to an agent; descriptions
    are written by the server, not by this platform.
    """
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = MCPServerService(get_transaction())
        try:
            tools = await discover_mcp_server(
                service=service,
                organization_id=organization_id,
                server_id=server_id,
                actor_id=current_user.member_id,
            )
        except MCPServerNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except MCPServerError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        return {
            "count": len(tools),
            "tools": [
                {
                    "id": str(tool.id),
                    "wire_id": tool.wire_id,
                    "slug": tool.slug,
                    "name": tool.name,
                    "description": tool.description,
                    "effect": MCPToolExecutorConfig.model_validate(
                        tool.executor_config
                    ).effect.value,
                    "execution_mode": tool.execution_mode,
                    "lifecycle": tool.lifecycle,
                    "published_revision": tool.published_revision,
                }
                for tool in tools
            ],
        }


@router.patch("/{server_id}")
async def update_mcp_server(
    organization_id: UUID,
    server_id: UUID,
    request: MCPServerPatch,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Patch endpoint metadata or encrypted header secrets, then rediscover."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = MCPServerService(get_transaction())
        try:
            server = await service.update(
                organization_id=organization_id,
                server_id=server_id,
                expected_draft_version=request.expected_draft_version,
                name=request.name,
                url=request.url,
                header_patch=request.headers,
            )
        except MCPServerNotFoundError as error:
            raise HTTPException(status_code=404) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except MCPServerError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return redacted_server(server)


@router.post("/{server_id}/withdraw")
async def withdraw_mcp_server(
    organization_id: UUID,
    server_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Stop offering this server's tools for new Agent revisions."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        try:
            server = await MCPServerService(get_transaction()).withdraw(
                organization_id=organization_id,
                server_id=server_id,
            )
        except MCPServerNotFoundError as error:
            raise HTTPException(status_code=404) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return redacted_server(server)


@router.post("/{server_id}/revisions/{revision}/revoke")
async def revoke_mcp_server_revision(
    organization_id: UUID,
    server_id: UUID,
    revision: int,
    request: MCPServerRevoke,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Emergency-stop an exact server revision."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        try:
            row = await MCPServerService(get_transaction()).revoke_revision(
                organization_id=organization_id,
                server_id=server_id,
                revision=revision,
                actor_id=current_user.member_id,
                reason=request.reason,
            )
        except MCPServerNotFoundError as error:
            raise HTTPException(status_code=404) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "server_id": str(row.server_id),
            "revision": row.revision,
            "availability": row.availability,
            "revoked_at": row.revoked_at,
            "revoked_by": str(row.revoked_by) if row.revoked_by else None,
            "revocation_reason": row.revocation_reason,
            "cancellation_requested_at": row.cancellation_requested_at,
        }
