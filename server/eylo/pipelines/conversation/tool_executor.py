"""Framework adapter for current platform tool execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

from eylo.framework.agents.context import RunContext
from eylo.framework.agents.tool import ToolCall, ToolResult
from eylo.modules.agents.services.tool_execution_utils import (
    AmbiguousModelToolNameError,
    ModelToolNotFoundError,
    ToolApprovalRequiredError,
    ToolExecutionBlockedError,
    require_tool_execution_allowed,
    resolve_model_tool,
)
from eylo.modules.conversations.constants import HANDOFF_TOOL_PREFIX
from eylo.modules.tools.models import ToolKind
from eylo.pipelines.conversation.tool_dispatch import (
    execute_handoff,
    execute_registered_tool,
)
from eylo.pipelines.email.tool_execution import (
    SEND_EMAIL_TOOL_NAME,
    execute_agent_email_tool,
)
from eylo.pipelines.integrations_v2.execution import execute_curated_tool
from eylo.pipelines.mcp.tool_execution import execute_mcp_tool
from eylo.pipelines.sandbox.tool_execution import (
    SANDBOX_TOOL_SLUGS,
    execute_agent_sandbox_tool,
)
from eylo.pipelines.telephony.tool_execution import (
    PLACE_CALL_TOOL_NAME,
    execute_agent_place_call_tool,
)
from eylo.pipelines.voice.end_call import (
    END_CALL_TOOL_NAME,
    execute_agent_end_call_tool,
    is_live_voice_session_active,
)
from eylo.pipelines.voice.live_buffer import LiveVoiceBufferIdentity
from eylo.sockets.llm import LLMToolUseBlock

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.pipelines.outbound.durable_execution import DurableStepContext
    from eylo.sockets.email.sendgrid import SendGridHttpTransport
    from eylo.sockets.mcp.client import MCPHttpTransport


class PlatformToolExecutor:
    """Execute framework tool calls through platform-owned dispatch."""

    def __init__(
        self,
        *,
        mcp_transport: MCPHttpTransport | None = None,
        email_transport: SendGridHttpTransport | None = None,
    ) -> None:
        self._mcp_transport = mcp_transport
        self._email_transport = email_transport

    async def execute(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> ToolResult:
        """Execute one tool call using current platform dispatch."""
        conversation_context = _conversation_context_from(context.local_context)
        await _refresh_tool_availability(conversation_context, context.local_context)
        block = LLMToolUseBlock(
            id=call.id,
            name=call.name,
            input=call.arguments,
        )

        if call.name.startswith(HANDOFF_TOOL_PREFIX):
            source_participant = conversation_context.get_primary_agent()
            outcome = await execute_handoff(conversation_context, block)
            new_agent = outcome.target_agent
            new_participant = outcome.target_participant
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=not outcome.succeeded,
                metadata={
                    "handoff_context_changed": bool(new_agent or new_participant),
                    "handoff_occurred": outcome.succeeded,
                    "handoff_outcome": (
                        "succeeded" if outcome.succeeded else "rejected"
                    ),
                    "swarm_id": str(conversation_context.conversation.swarm_id)
                    if conversation_context.conversation.swarm_id
                    else None,
                    "swarm_revision": conversation_context.conversation.swarm_revision,
                    "source_agent_id": str(outcome.source_agent.id),
                    "source_agent_revision": source_participant.agent_revision
                    if source_participant
                    else None,
                    "source_participant_id": str(source_participant.id)
                    if source_participant
                    else None,
                    "new_agent_id": str(new_agent.id) if new_agent else None,
                    "new_agent_revision": new_participant.agent_revision
                    if new_participant
                    else None,
                    "new_participant_id": str(new_participant.id)
                    if new_participant
                    else None,
                    "target_agent_id": str(new_agent.id) if new_agent else None,
                    "target_agent_revision": new_participant.agent_revision
                    if new_participant
                    else None,
                    "target_participant_id": str(new_participant.id)
                    if new_participant
                    else None,
                    "circuit_breaker_triggered": outcome.circuit_breaker_triggered,
                    "handoff_loop_detected": outcome.handoff_loop_detected,
                    "terminal_response": outcome.circuit_breaker_triggered,
                    "terminal_output": (
                        outcome.content if outcome.circuit_breaker_triggered else None
                    ),
                },
            )

        try:
            requested_tool = resolve_model_tool(
                conversation_context.get_tools(),
                call.name,
            )
        except (ModelToolNotFoundError, AmbiguousModelToolNameError):
            return ToolResult(
                tool_call_id=call.id,
                content={
                    "kind": "integration_error",
                    "error": "tool_not_available",
                },
                is_error=True,
            )
        if (
            requested_tool.kind is ToolKind.SYSTEM
            and requested_tool.slug == END_CALL_TOOL_NAME
        ):
            live_voice_identity = _live_voice_identity_from(
                context.local_context,
                conversation_context,
            )
            if live_voice_identity is not None:
                outcome = await execute_agent_end_call_tool(
                    conversation_context=conversation_context,
                    identity=live_voice_identity,
                )
                return ToolResult(
                    tool_call_id=call.id,
                    content=outcome.content,
                    is_error=outcome.is_error,
                    metadata=outcome.metadata,
                )
        if (
            requested_tool.kind is ToolKind.SYSTEM
            and requested_tool.slug in SANDBOX_TOOL_SLUGS
        ):
            state = _durable_execution_state(context.local_context, call.id)
            agent_run_id = _agent_run_id_from(context.local_context)
            if state is None or agent_run_id is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "success": False,
                        "error": "durable_agent_run_required",
                        "message": (
                            "Sandbox work requires a durable agent run and is "
                            "unavailable in live voice."
                        ),
                    },
                    is_error=True,
                    metadata={
                        "sandbox_execution": True,
                        "sandbox_failure_code": "durable_agent_run_required",
                    },
                )
            tool_use_message_id, durable_context = state
            agent = conversation_context.primary_agent
            outcome = await execute_agent_sandbox_tool(
                tool_slug=requested_tool.slug,
                tool_input=call.arguments,
                organization_id=conversation_context.conversation.organization_id,
                agent_id=agent.id,
                agent_run_id=agent_run_id,
                tool_command_id=tool_use_message_id,
                durable_context=durable_context,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=outcome.is_error,
                metadata=outcome.metadata,
            )
        if (
            requested_tool.kind is ToolKind.SYSTEM
            and requested_tool.slug == SEND_EMAIL_TOOL_NAME
        ):
            state = _durable_execution_state(context.local_context, call.id)
            if state is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "kind": "email_error",
                        "error": "durable_execution_required",
                    },
                    is_error=True,
                    metadata={"email_delivery": True},
                )
            tool_use_message_id, durable_context = state
            outcome = await execute_agent_email_tool(
                tool_input=call.arguments,
                conversation_context=conversation_context,
                tool_use_message_id=tool_use_message_id,
                durable_context=durable_context,
                sendgrid_transport=self._email_transport,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=outcome.is_error,
                metadata=dict(outcome.metadata),
            )
        if (
            requested_tool.kind is ToolKind.SYSTEM
            and requested_tool.slug == PLACE_CALL_TOOL_NAME
        ):
            state = _durable_execution_state(context.local_context, call.id)
            if state is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "kind": "telephony_error",
                        "error": "durable_execution_required",
                    },
                    is_error=True,
                    metadata={"telephony_delivery": True},
                )
            tool_use_message_id, durable_context = state
            outcome = await execute_agent_place_call_tool(
                tool_input=call.arguments,
                conversation_context=conversation_context,
                tool_use_message_id=tool_use_message_id,
                durable_context=durable_context,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=outcome.is_error,
                metadata=dict(outcome.metadata),
            )
        if requested_tool.kind is ToolKind.CURATED:
            # Policy is not enforced here. A curated tool's definition is code
            # and cannot change under a running deployment, so the only mutable
            # fact is operator policy — and the module service reads it live
            # while resolving the grant, before any client exists.
            state = _durable_execution_state(context.local_context, call.id)
            if state is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "kind": "curated_error",
                        "error": "durable_execution_required",
                    },
                    is_error=True,
                    metadata={"curated_execution": True},
                )
            tool_use_message_id, durable_context = state
            outcome = await execute_curated_tool(
                tool_id=UUID(str(requested_tool.id)),
                tool_input=call.arguments,
                conversation_context=conversation_context,
                tool_use_message_id=tool_use_message_id,
                durable_context=durable_context,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=outcome.is_error,
                metadata=dict(outcome.metadata),
            )
        if requested_tool.kind is ToolKind.MCP:
            try:
                require_tool_execution_allowed(requested_tool)
            except (ToolExecutionBlockedError, ToolApprovalRequiredError) as error:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "kind": "integration_error",
                        "error": "tool_execution_blocked",
                    },
                    is_error=True,
                    metadata={"tool_policy_error": type(error).__name__},
                )
            state = _durable_execution_state(context.local_context, call.id)
            if state is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content={
                        "kind": "integration_error",
                        "error": "durable_execution_required",
                    },
                    is_error=True,
                    metadata={"mcp_execution": True},
                )
            tool_use_message_id, durable_context = state
            outcome = await execute_mcp_tool(
                tool=requested_tool,
                tool_input=call.arguments,
                conversation_context=conversation_context,
                tool_use_message_id=tool_use_message_id,
                durable_context=durable_context,
                transport=self._mcp_transport,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=outcome.content,
                is_error=outcome.is_error,
                metadata=dict(outcome.metadata),
            )

        content = await execute_registered_tool(conversation_context, block)
        return ToolResult(tool_call_id=call.id, content=content)


def _conversation_context_from(local_context: object | None) -> ConversationContext:
    """Extract ConversationContext from the run's local context."""
    if local_context is None:
        raise ValueError("Platform tool execution requires a ConversationContext.")

    if hasattr(local_context, "primary_agent") and hasattr(
        local_context, "conversation"
    ):
        return local_context  # type: ignore[return-value]

    if isinstance(local_context, dict):
        value = local_context.get("conversation_context")
        if value is not None:
            return _conversation_context_from(value)

    raise ValueError(
        "Platform tool execution requires local_context to be a "
        "ConversationContext or {'conversation_context': ConversationContext}."
    )


def _durable_execution_state(
    local_context: object | None,
    tool_call_id: str,
) -> tuple[UUID, DurableStepContext] | None:
    if not isinstance(local_context, dict):
        return None
    durable_context = local_context.get("durable_context")
    tool_use_messages = local_context.get("tool_use_messages")
    if durable_context is None or not isinstance(tool_use_messages, dict):
        return None
    message = tool_use_messages.get(tool_call_id)
    message_id = getattr(message, "id", None)
    if message_id is None:
        return None
    return UUID(str(message_id)), cast("DurableStepContext", durable_context)


def _agent_run_id_from(local_context: object | None) -> UUID | None:
    if not isinstance(local_context, dict):
        return None
    value = local_context.get("agent_run_id")
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _live_voice_identity_from(
    local_context: object | None,
    conversation_context: ConversationContext,
) -> LiveVoiceBufferIdentity | None:
    if not isinstance(local_context, dict):
        return None
    identity = local_context.get("live_voice_identity")
    if not isinstance(identity, LiveVoiceBufferIdentity):
        return None
    conversation = conversation_context.conversation
    if (
        identity.organization_id != conversation.organization_id
        or identity.conversation_id != conversation.id
    ):
        return None
    return identity


async def _refresh_tool_availability(
    conversation_context: ConversationContext,
    local_context: object | None,
) -> None:
    """Re-check mutable tool requirements immediately before dispatch."""
    from eylo.common.contracts.tool_availability import ToolRuntimeFact
    from eylo.pipelines.system_tools.availability import (
        refresh_context_tool_availability,
    )

    runtime_facts: set[ToolRuntimeFact] = set()
    if isinstance(local_context, dict):
        if local_context.get("durable_context") is not None:
            runtime_facts.add(ToolRuntimeFact.DURABLE_EXECUTION)
        if _agent_run_id_from(local_context) is not None:
            runtime_facts.add(ToolRuntimeFact.AGENT_RUN)
        live_voice_identity = _live_voice_identity_from(
            local_context,
            conversation_context,
        )
        if (
            live_voice_identity is not None
            and await is_live_voice_session_active(live_voice_identity)
        ):
            runtime_facts.add(ToolRuntimeFact.ACTIVE_VOICE_SESSION)
    await refresh_context_tool_availability(
        conversation_context,
        runtime_facts=runtime_facts,
    )
