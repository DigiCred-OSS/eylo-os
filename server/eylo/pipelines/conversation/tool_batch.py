"""Batch conversational tool execution helpers.

Classifies tool calls (simple vs handoff vs widget), dispatches
execution, and returns structured results.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eylo.common.contracts.llm_response import LLMContentType, LLMToolUseBlock
from eylo.common.database import start_transaction
from eylo.common.instrumentation import tool_span
from eylo.modules.agents.services.runner.message_store import (
    format_widget_render_fallback,
)
from eylo.modules.conversations.constants import HANDOFF_TOOL_PREFIX, WIDGET_TOOL_PREFIX
from eylo.pipelines.conversation.tool_dispatch import (
    execute_handoff,
    execute_registered_tool,
)

if TYPE_CHECKING:
    from eylo.common.contracts.llm_response import LLMResponse
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.modules.conversations.schemas.messages import MessageInDb

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Result of a single tool execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    tool_use_block: Any  # LLMToolUseBlock
    tool_use_message: Optional[Any] = None  # MessageInDb
    result: str | dict | list = ""
    is_error: bool = False
    error_message: Optional[str] = None
    is_widget_fallback: bool = False


class HandoffResult(BaseModel):
    """Result when a handoff tool is executed."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    from_agent: Optional[Any] = None  # AgentInDb
    to_agent: Optional[Any] = None  # AgentInDb
    to_participant: Any = None
    tool_use_block: Any = None
    tool_result: str = ""
    requested_input: Optional[str] = None
    is_error: bool = False
    circuit_breaker_triggered: bool = False
    handoff_loop_detected: bool = False


class ToolBatchResult(BaseModel):
    """Result of executing a batch of tool calls from one LLM turn."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    results: List[ToolResult] = Field(default_factory=list)
    handoff: Optional[HandoffResult] = None

    @property
    def has_handoff(self) -> bool:
        return (
            self.handoff is not None
            and not self.handoff.is_error
            and self.handoff.to_agent is not None
            and self.handoff.to_participant is not None
            and not self.handoff.circuit_breaker_triggered
            and not self.handoff.handoff_loop_detected
        )


class ConversationToolBatchExecutor:
    """Execute persisted tool calls from one conversational model turn."""

    @staticmethod
    def extract_tool_calls(llm_response: LLMResponse) -> list[LLMToolUseBlock]:
        """Extract tool_use blocks from an LLM response."""
        blocks = []
        for content in llm_response.content:
            if LLMContentType(content.type) == LLMContentType.TOOL_USE:
                blocks.append(content.content)
        return blocks

    @staticmethod
    def parse_tool_use_block(tool_use_message: MessageInDb) -> LLMToolUseBlock | None:
        """Parse a TOOL_USE message into an LLMToolUseBlock."""
        try:
            parsed_content = tool_use_message.get_tool_use_content()
            return LLMToolUseBlock.model_validate(parsed_content.content.model_dump())
        except (AttributeError, ValidationError, ValueError) as error:
            logger.warning(
                "Failed to parse tool use content error_type=%s",
                type(error).__name__,
            )
            return None

    @staticmethod
    def is_handoff_tool(tool_name: str) -> bool:
        return tool_name.startswith(HANDOFF_TOOL_PREFIX)

    @staticmethod
    def _is_widget_tool(tool_name: str) -> bool:
        return tool_name.startswith(WIDGET_TOOL_PREFIX)

    def classify_tool_messages(
        self,
        tool_messages: list[MessageInDb],
    ) -> tuple[
        list[tuple[MessageInDb, Any]],
        list[tuple[MessageInDb, Any]],
    ]:
        """Split tool messages into concurrent (safe for gather) and sequential.

        Returns (concurrent, sequential) tuples of (message, block).
        """
        concurrent = []
        sequential = []

        for msg in tool_messages:
            block = self.parse_tool_use_block(msg)
            if not block:
                continue

            if self.is_handoff_tool(block.name) or self._is_widget_tool(block.name):
                sequential.append((msg, block))
            else:
                concurrent.append((msg, block))

        return concurrent, sequential

    async def execute_simple_tool(
        self,
        ctx: ConversationContext,
        tool_use_block: LLMToolUseBlock,
    ) -> str | dict | list:
        """Execute a simple (non-handoff) registered tool."""
        return await execute_registered_tool(ctx, tool_use_block)

    async def execute_simple_tool_isolated(
        self,
        ctx: ConversationContext,
        tool_use_block: LLMToolUseBlock,
    ) -> ToolResult:
        """Execute a simple tool in its own transaction (for asyncio.gather).

        Each call gets its own DB session so concurrent credential
        lookups don't collide on a shared AsyncSession.

        Wrapped in a Sentry ``gen_ai.execute_tool`` span for AI monitoring.
        """
        try:
            with tool_span("tool_execution"):
                async with start_transaction():
                    result = await self.execute_simple_tool(ctx, tool_use_block)
            return ToolResult(
                tool_name=tool_use_block.name,
                tool_use_block=tool_use_block,
                result=result,
            )
        except Exception as error:
            logger.warning(
                "Tool execution failed error_type=%s",
                type(error).__name__,
            )
            is_widget = self._is_widget_tool(tool_use_block.name)
            return ToolResult(
                tool_name=tool_use_block.name,
                tool_use_block=tool_use_block,
                result="",
                is_error=True,
                error_message="Tool execution failed.",
                is_widget_fallback=is_widget,
            )

    async def execute_handoff_tool(
        self,
        ctx: ConversationContext,
        tool_use_block: LLMToolUseBlock,
    ) -> HandoffResult:
        """Execute a handoff tool and project its current outcome."""
        try:
            with tool_span("handoff_execution"):
                outcome = await execute_handoff(ctx, tool_use_block)

            return HandoffResult(
                from_agent=outcome.source_agent,
                to_agent=outcome.target_agent,
                to_participant=outcome.target_participant,
                tool_use_block=tool_use_block,
                tool_result=outcome.content,
                requested_input=outcome.requested_input,
                is_error=not outcome.succeeded,
                circuit_breaker_triggered=outcome.circuit_breaker_triggered,
                handoff_loop_detected=outcome.handoff_loop_detected,
            )
        except Exception as error:
            logger.warning(
                "Handoff tool execution failed error_type=%s",
                type(error).__name__,
            )
            return HandoffResult(
                from_agent=ctx.primary_agent,
                tool_use_block=tool_use_block,
                tool_result="Error: Agent handoff failed.",
                is_error=True,
                circuit_breaker_triggered=True,
            )

    async def execute_batch(
        self,
        run_ctx: Any,
        tool_messages: list[MessageInDb],
        parallel: bool = True,
    ) -> ToolBatchResult:
        """Execute a batch of tool calls from one LLM turn.

        Non-handoff tools execute concurrently when parallel=True.
        Handoff/widget tools always execute sequentially.
        """
        ctx = run_ctx.conversation_context
        concurrent, sequential = self.classify_tool_messages(tool_messages)
        batch = ToolBatchResult()
        widget_fallback_occurred = False

        # Execute non-handoff tools (potentially in parallel)
        if concurrent:
            if parallel:
                results = await asyncio.gather(
                    *[
                        self.execute_simple_tool_isolated(ctx, block)
                        for _, block in concurrent
                    ]
                )
            else:
                results = []
                for _, block in concurrent:
                    r = await self.execute_simple_tool_isolated(ctx, block)
                    results.append(r)

            for (msg, _block), result in zip(concurrent, results):
                result.tool_use_message = msg
                if result.is_widget_fallback:
                    widget_fallback_occurred = True
                batch.results.append(result)

        # Execute handoff/widget tools sequentially
        for msg, block in sequential:
            if self.is_handoff_tool(block.name):
                handoff = await self.execute_handoff_tool(ctx, block)
                handoff_result = ToolResult(
                    tool_name=block.name,
                    tool_use_block=block,
                    tool_use_message=msg,
                    result=handoff.tool_result,
                    is_error=handoff.is_error,
                )
                batch.results.append(handoff_result)
                # Always store the outcome; callers inspect the explicit result.
                batch.handoff = handoff
            elif self._is_widget_tool(block.name) and widget_fallback_occurred:
                # Skip widget tool after a prior widget fallback in this turn
                batch.results.append(
                    ToolResult(
                        tool_name=block.name,
                        tool_use_block=block,
                        tool_use_message=msg,
                        result=format_widget_render_fallback(),
                        is_error=True,
                        is_widget_fallback=True,
                    )
                )
            else:
                # Widget or other sequential tool
                try:
                    with tool_span("tool_execution"):
                        result_str = await self.execute_simple_tool(ctx, block)
                    batch.results.append(
                        ToolResult(
                            tool_name=block.name,
                            tool_use_block=block,
                            tool_use_message=msg,
                            result=result_str,
                        )
                    )
                except Exception as error:
                    logger.warning(
                        "Sequential tool failed error_type=%s",
                        type(error).__name__,
                    )
                    is_widget = self._is_widget_tool(block.name)
                    if is_widget:
                        widget_fallback_occurred = True
                    batch.results.append(
                        ToolResult(
                            tool_name=block.name,
                            tool_use_block=block,
                            tool_use_message=msg,
                            is_error=True,
                            error_message="Tool execution failed.",
                            is_widget_fallback=is_widget,
                        )
                    )

        return batch
