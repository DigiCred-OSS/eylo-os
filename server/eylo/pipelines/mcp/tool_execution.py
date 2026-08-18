"""Application service for exact tenant MCP tool execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

from eylo.common.database import get_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.mcp_servers.service import MCPServerError, MCPServerService
from eylo.modules.tools.models import ToolKind
from eylo.modules.tools.schemas.executors.mcp import (
    MCPToolEffect,
    validate_mcp_tool_executor_config,
)
from eylo.pipelines.outbound.durable_execution import DurableStepContext
from eylo.sockets.mcp.client import MCPHttpTransport

from .execution import MCPToolExecutionOutcome, execute_mcp_operation
from .tools import MCPToolError, server_config

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.modules.tools.schemas.indb import ToolInDb


async def execute_mcp_tool(
    *,
    tool: ToolInDb,
    tool_input: Mapping[str, Any],
    conversation_context: ConversationContext,
    tool_use_message_id: UUID | None,
    durable_context: DurableStepContext | None,
    transport: MCPHttpTransport | None = None,
) -> MCPToolExecutionOutcome:
    """Resolve exact published server/tool revisions and execute their contract."""
    if tool.kind is not ToolKind.MCP:
        raise ValueError("MCP tool execution requires ToolKind.MCP.")
    try:
        executor = validate_mcp_tool_executor_config(tool.executor_config)
    except ValueError:
        return _unavailable("mcp_configuration_invalid")
    if executor.effect is MCPToolEffect.UNSUPPORTED:
        return _unavailable("mcp_effect_unsupported")
    if (
        tool.mcp_server_id is None
        or tool.mcp_server_revision is None
        or tool.published_revision is None
    ):
        return _unavailable(
            "mcp_configuration_invalid",
            effect=executor.effect,
        )

    organization_id = UUID(str(conversation_context.conversation.organization_id))
    server_id = UUID(str(tool.mcp_server_id))
    try:
        server = await MCPServerService(get_transaction()).get_revision(
            organization_id=organization_id,
            server_id=server_id,
            revision=tool.mcp_server_revision,
        )
        config = server_config(
            server.config,
            organization_id=organization_id,
            server_id=server_id,
            revision=tool.mcp_server_revision,
        )
    except (DefinitionRevisionError, MCPServerError, MCPToolError):
        return _unavailable(
            "mcp_configuration_invalid",
            effect=executor.effect,
        )

    return await execute_mcp_operation(
        config=config,
        executor=executor,
        arguments=tool_input,
        organization_id=organization_id,
        tool_use_message_id=tool_use_message_id,
        tool_id=UUID(str(tool.id)),
        tool_revision=tool.published_revision,
        server_id=server_id,
        server_revision=tool.mcp_server_revision,
        durable_context=durable_context,
        transport=transport,
    )


def _unavailable(
    code: str,
    *,
    effect: MCPToolEffect = MCPToolEffect.UNSUPPORTED,
) -> MCPToolExecutionOutcome:
    return MCPToolExecutionOutcome(
        effect=effect,
        failure_code=code,
    )


__all__ = ["execute_mcp_tool"]
