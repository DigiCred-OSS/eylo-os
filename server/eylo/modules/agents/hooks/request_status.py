"""Project Agent-run lifecycle callbacks onto canonical request status."""

import logging
from typing import Optional

from eylo.common.database import get_transaction
from eylo.modules.agents.hooks.types import (
    PRE_LOOP_ITERATION,
    AgentInDb,
    HookContext,
    RunHooks,
)
from eylo.modules.conversations.schemas.messages import (
    MessageInDb,
    RequestStatus,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.tools.schemas.indb import ToolInDb

logger = logging.getLogger(__name__)


class RequestStatusHooks(RunHooks):
    """Manages request status transitions at lifecycle boundaries.

    Status lifecycle::

        PENDING → PROCESSING → [AWAITING_TOOL_RESULTS → PROCESSING]* → COMPLETED
        Any state → FAILED (on error)
        Any state → INTERRUPTED (external — not managed by hooks)

    """

    def __init__(self, message_service: MessageService) -> None:
        self._message_service = message_service

    async def _set_status(self, context: HookContext, status: RequestStatus) -> None:
        """Update request status and commit."""
        await self._message_service.update_request_status_by_request_id(
            request_id=context.request_id,
            request_status=status,
            conversation_id=context.user_message.conversation_id,
        )
        await get_transaction().commit()

    async def on_agent_start(self, context: HookContext, agent: AgentInDb) -> None:
        """Set PENDING when the run starts (before the loop begins)."""
        if context.iteration == PRE_LOOP_ITERATION:
            await self._set_status(context, RequestStatus.PENDING)

    async def on_llm_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        system_prompt: Optional[str],
        messages: list[MessageInDb],
        tools: list[ToolInDb],
    ) -> None:
        """Set PROCESSING before each LLM call."""
        await self._set_status(context, RequestStatus.PROCESSING)

    async def on_tool_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        tool_input: dict,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Set AWAITING_TOOL_RESULTS when tools begin executing.

        Note: The original code sets this once per tool batch, not per tool.
        This hook fires per-tool. The status update is idempotent — setting
        AWAITING_TOOL_RESULTS multiple times in the same batch is harmless.
        """
        await self._set_status(context, RequestStatus.AWAITING_TOOL_RESULTS)

    async def on_agent_end(
        self, context: HookContext, agent: AgentInDb, output: MessageInDb
    ) -> None:
        """Set COMPLETED when the agent produces a final output."""
        await self._set_status(context, RequestStatus.COMPLETED)

    async def on_agent_error(
        self, context: HookContext, agent: AgentInDb, error: Exception
    ) -> None:
        """Set FAILED when the agent encounters an error."""
        await self._set_status(context, RequestStatus.FAILED)
