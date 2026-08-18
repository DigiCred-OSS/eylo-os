"""Emit correlated Agent lifecycle events from run-hook callbacks."""

import logging

from eylo.events.py_events.agent_lifecycle import AgentLifecycleEmitter
from eylo.events.schema.py_events.base import (
    AgentLifecycleOutcome,
    AgentProcessingEvent,
    AgentResponseCompleteEvent,
    AgentRunInferenceEvent,
    AgentRunToolEvent,
    AgentToolResponseEvent,
)
from eylo.modules.agents.hooks.types import AgentInDb, HookContext, RunHooks
from eylo.modules.conversations.schemas.messages import MessageInDb
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformToolResult

logger = logging.getLogger(__name__)


class EventBroadcastHooks(RunHooks):
    """Emits py_events at lifecycle boundaries for WebSocket broadcasting.

    Events are consumed by agent_lifecycle.py listener which broadcasts
    corresponding WebSocket events to connected clients.
    """

    def __init__(self) -> None:
        self._events = AgentLifecycleEmitter()

    async def on_agent_start(self, context: HookContext, agent: AgentInDb) -> None:
        """Emit AgentProcessingEvent + AgentRunInferenceEvent."""
        self._events.emit(
            AgentProcessingEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=context.user_message.id,
        )
        self._events.emit(
            AgentRunInferenceEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=context.user_message.id,
        )

    async def on_agent_end(
        self, context: HookContext, agent: AgentInDb, output: MessageInDb
    ) -> None:
        """Emit AgentResponseCompleteEvent on successful completion."""
        self._events.emit(
            AgentResponseCompleteEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=context.user_message.id,
            outcome=AgentLifecycleOutcome.COMPLETED,
        )

    async def on_agent_error(
        self, context: HookContext, agent: AgentInDb, error: Exception
    ) -> None:
        """Emit AgentResponseCompleteEvent on error (UI recovery).

        The widget needs this event to re-enable the input field regardless
        of whether the agent succeeded or failed.
        """
        self._events.emit(
            AgentResponseCompleteEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=context.user_message.id,
            outcome=AgentLifecycleOutcome.FAILED,
        )

    async def on_tool_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        tool_input: dict,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Emit AgentRunToolEvent."""
        event_message = tool_use_message if tool_use_message else context.user_message
        self._events.emit(
            AgentRunToolEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=event_message.id,
        )

    async def on_tool_end(
        self,
        context: HookContext,
        agent: AgentInDb,
        tool: ToolInDb,
        result: PlatformToolResult,
        tool_use_message: MessageInDb | None = None,
    ) -> None:
        """Emit AgentToolResponseEvent."""
        event_message = tool_use_message if tool_use_message else context.user_message
        self._events.emit(
            AgentToolResponseEvent,
            context=context.conversation_context,
            request_id=context.request_id,
            message_id=event_message.id,
        )

    async def on_turn_start(
        self,
        context: HookContext,
        agent: AgentInDb,
        turn: int,
    ) -> None:
        """Emit AgentRunInferenceEvent at the start of each turn.

        Signals to the UI that the agent is about to call the LLM again
        (useful after tool execution rounds).
        """
        if turn > 1:
            self._events.emit(
                AgentRunInferenceEvent,
                context=context.conversation_context,
                request_id=context.request_id,
                message_id=context.user_message.id,
            )
