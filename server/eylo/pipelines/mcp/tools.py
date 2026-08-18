"""Compose MCP server state, the safe HTTP socket, and tool synchronization."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.modules.mcp_servers.config import (
    ResolvedMCPServerConfig,
    resolve_mcp_server_config,
)
from eylo.modules.mcp_servers.service import (
    MCPServerError,
    MCPServerService,
)
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.tools.models import ToolModel
from eylo.sockets.http.transport import SafeHttpTransport
from eylo.sockets.mcp.client import (
    MCPClient,
    MCPError,
    MCPHttpTransport,
)


class MCPToolError(Exception):
    """Safe application-level MCP failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def server_config(
    config: dict[str, Any] | None,
    *,
    organization_id: UUID,
    server_id: UUID,
    revision: int,
) -> ResolvedMCPServerConfig:
    """Decrypt one exact tenant/server/revision-bound MCP config."""
    try:
        return resolve_mcp_server_config(
            config,
            organization_id=organization_id,
            server_id=server_id,
            revision=revision,
        )
    except (ProviderConfigError, SecretCipherError, ValueError):
        raise MCPToolError(
            "configuration_unavailable",
            "MCP server configuration is unavailable.",
        ) from None


async def discover_tools(
    *,
    config: ResolvedMCPServerConfig,
    transport: MCPHttpTransport | None = None,
) -> list[dict[str, Any]]:
    """Return one complete, bounded, successful `tools/list` snapshot."""
    try:
        tools = await MCPClient(
            url=config.url,
            origin_headers=config.origin_headers,
            transport=transport or SafeHttpTransport(),
        ).list_tools()
    except MCPError as error:
        raise MCPToolError(
            error.code,
            "MCP discovery failed.",
            retryable=error.retryable,
        ) from None
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "annotations": tool.annotations,
        }
        for tool in tools
    ]


async def discover_mcp_server(
    *,
    service: MCPServerService,
    organization_id: UUID,
    server_id: UUID,
    actor_id: UUID,
    transport: MCPHttpTransport | None = None,
) -> list[ToolModel]:
    """Resolve, contact, validate, and atomically synchronize one server."""
    target = await service.prepare_discovery(
        organization_id=organization_id,
        server_id=server_id,
    )
    try:
        discovered = await discover_tools(
            config=target.config,
            transport=transport,
        )
    except MCPToolError as error:
        raise MCPServerError(str(error)) from None
    return await service.synchronize_discovery(
        organization_id=organization_id,
        target=target,
        actor_id=actor_id,
        discovered=discovered,
    )


__all__ = [
    "MCPToolError",
    "discover_mcp_server",
    "discover_tools",
    "server_config",
]
