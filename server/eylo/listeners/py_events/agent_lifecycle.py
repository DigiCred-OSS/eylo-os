"""Project correlated agent lifecycle events onto WebSocket UI deltas.

These handlers are presentation-only. Runtime work and terminal persistence
complete before the corresponding event is emitted. Each payload carries a
request ID, run ID, run start time, and monotonic sequence so clients can reject
late or reordered delivery.
"""

import logging

from eylo.events.schema.py_events.base import (
    AgentProcessingEvent,
    AgentResponseCompleteEvent,
    AgentRunInferenceEvent,
    AgentRunToolEvent,
    AgentToolResponseEvent,
)
from eylo.listeners.py_events.utils import broadcast_to_conversation_contacts
from eylo.pipelines.websocket.schemas import WsEventAction

logger = logging.getLogger(__name__)


def _lifecycle_payload(event, *, status: str, message: str | None = None) -> dict:
    payload = {
        "conversation_id": str(event.conversation_id),
        "message_id": str(event.message_id) if event.message_id else None,
        "request_id": str(event.request_id),
        "run_id": str(event.run_id),
        "run_started_at": event.run_started_at.isoformat(),
        "sequence": event.sequence,
        "terminal": isinstance(event, AgentResponseCompleteEvent),
        "status": status,
    }
    if message:
        payload["message"] = message
    if isinstance(event, AgentResponseCompleteEvent):
        payload["outcome"] = event.outcome.value
    return payload


async def _broadcast(event, *, kind: WsEventAction, status: str, message: str | None):
    await broadcast_to_conversation_contacts(
        contact_ids=event.contact_ids,
        organization_id=event.organization_id,
        conversation_id=event.conversation_id,
        kind=kind,
        payload=_lifecycle_payload(event, status=status, message=message),
        event_name=status.replace("_", " ").title(),
    )


async def handle_agent_thinking(event: AgentRunInferenceEvent):
    """Broadcast that the current run entered LLM inference."""
    await _broadcast(
        event,
        kind=WsEventAction.AGENT_THINKING,
        status="thinking",
        message="Thinking...",
    )


async def handle_agent_processing(event: AgentProcessingEvent):
    """Broadcast that the agent accepted and started processing the request."""
    await _broadcast(
        event,
        kind=WsEventAction.AGENT_PROCESSING,
        status="processing",
        message="Processing...",
    )


async def handle_tool_executing(event: AgentRunToolEvent):
    """Broadcast tool executing event when agent starts a tool call.

    Shows users which tool the agent is using in real-time.
    """
    await _broadcast(
        event,
        kind=WsEventAction.TOOL_EXECUTING,
        status="tool_executing",
        message="Using tools...",
    )


async def handle_tool_completed(event: AgentToolResponseEvent):
    """Broadcast tool completed event when tool execution finishes.

    Signals to the widget that the tool has finished and agent is processing results.
    """
    await _broadcast(
        event,
        kind=WsEventAction.TOOL_COMPLETED,
        status="tool_completed",
        message="Analyzing results...",
    )


async def handle_agent_response_complete(event: AgentResponseCompleteEvent):
    """Broadcast the completed or failed terminal state for the correlated run."""
    failed = event.outcome.value == "failed"
    await _broadcast(
        event,
        kind=WsEventAction.AGENT_RESPONSE_COMPLETE,
        status="error" if failed else "complete",
        message="The agent could not complete this request." if failed else None,
    )
