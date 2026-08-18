"""Production-facing conversation wrapper for the framework runner.

This adapter keeps the primitive ``FrameworkRunner`` free of Eylo persistence
concerns while giving the message listener a concrete execution seam.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import arrow
from pydantic import BaseModel, ConfigDict, Field

from eylo.common.context_compaction import (
    latest_context_compaction,
    uncompacted_messages,
)
from eylo.common.contracts.llm_response import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
)
from eylo.common.contracts.tool_platform import PlatformTool, PlatformToolInputSchema
from eylo.common.contracts.tool_record import ToolRecord
from eylo.common.database import get_transaction
from eylo.events.py_events.agent_lifecycle import AgentLifecycleEmitter
from eylo.events.schema.py_events.base import (
    AgentLifecycleOutcome,
    AgentProcessingEvent,
    AgentResponseCompleteEvent,
    AgentRunInferenceEvent,
    AgentRunToolEvent,
    AgentToolResponseEvent,
)
from eylo.framework.agents.agent import AgentSpec
from eylo.framework.agents.config import RunConfig
from eylo.framework.agents.context import RunContext, RunInput, RunMessage
from eylo.framework.agents.hooks import RunHooks
from eylo.framework.agents.model import (
    ModelBlockKind,
    ModelOutputBlock,
    ModelResponse,
    ModelSettings,
)
from eylo.framework.agents.result import RunStatus
from eylo.framework.agents.runner import FrameworkRunner
from eylo.framework.agents.tool import ToolCall, ToolExecutor, ToolResult, ToolSpec
from eylo.modules.agent_runs.budgets import (
    has_current_agent_run_budget_scope,
    meter_current_agent_run_usage,
)
from eylo.modules.agent_runs.domain import (
    AgentInputRequestKind,
    AgentRunLifecycle,
    AgentRunOutcome,
)
from eylo.modules.agent_runs.service import (
    AgentRunWaitState,
    finish_agent_run_in_transaction,
    pause_agent_run_in_transaction,
)
from eylo.modules.agents.services.runner.message_store import ErrorMessages
from eylo.modules.conversations.schemas.message_content import (
    AssistantMessageContent,
    SystemMessageContent,
    TextContent,
    TextMessageContentBlocks,
    ToolResultContent,
    ToolResultMessageContent,
    ToolUseContent,
    ToolUseMessageContent,
    UserMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
    RequestStatus,
)
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.conversation.background_dispatch import (
    dispatch_background_agents,
)
from eylo.pipelines.conversation.context import ConversationContextService
from eylo.pipelines.session_timeline import try_file_runtime_fact
from eylo.sockets.llm.factory import LLMFactory
from eylo.sockets.tts.text_stream import SpeakableTextBuffer

from .domain import (
    ExistingRunInputMetadata,
    ExistingToolCallMetadata,
    ExistingToolResultMetadata,
    agent_spec_from_context,
    run_input_from_context,
)
from .tool_executor import PlatformToolExecutor

if TYPE_CHECKING:
    from eylo.pipelines.outbound.durable_execution import DurableStepContext

logger = logging.getLogger(__name__)

_PAUSE_STATUSES = {
    RunStatus.WAITING_FOR_APPROVAL,
    RunStatus.WAITING_FOR_INPUT,
}

FRAMEWORK_META_FLAG = True
RUN_METADATA_KEY = "run_metadata"
APPROVAL_REQUEST_KEY = "approval_request"
INPUT_REQUEST_KEY = "input_request"
CONTINUATION_KEY = "continuation"
TERMINAL_RESPONSE_KEY = "terminal_response"
TERMINAL_TOOL_CALL_ID_KEY = "terminal_tool_call_id"
TERMINAL_OUTPUT_KEY = "terminal_output"


class FrameworkMessageMeta(BaseModel):
    """Typed meta for framework-created assistant/tool-use messages."""

    model_config = ConfigDict(extra="allow")

    framework: bool = FRAMEWORK_META_FLAG
    llm_response: dict[str, Any]
    model_response: dict[str, Any]


class FrameworkTerminalMessageMeta(BaseModel):
    """Typed meta for the final message persisted for a framework run."""

    model_config = ConfigDict(extra="allow")

    framework: bool = FRAMEWORK_META_FLAG
    run_id: str
    status: RunStatus
    model: str
    usage: dict[str, int]
    error: bool
    run_metadata: dict[str, Any] | None = None
    approval_request: dict[str, Any] | None = None
    input_request: dict[str, Any] | None = None
    continuation: dict[str, Any] | None = None
    terminal_response: bool | None = None
    terminal_tool_call_id: str | None = None


class FrameworkToolResultMeta(BaseModel):
    """Typed meta for framework-created tool result messages."""

    model_config = ConfigDict(extra="allow")

    framework: bool = FRAMEWORK_META_FLAG
    tool_call_id: str
    is_error: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _FrameworkToolRecord:
    """Vendor-facing record for a framework-only model tool."""

    id: UUID
    llm_config: PlatformTool


def _vendor_tools_from_run_input(
    run_input: RunInput,
    conversation_context: object,
) -> list[ToolRecord]:
    """Project the framework-authoritative tool list into vendor records."""
    persisted_by_name: dict[str, ToolRecord] = {}
    for tool in conversation_context.get_tools():
        name = tool.llm_config.name
        if name in persisted_by_name:
            raise ValueError("Conversation tools contain a duplicate model-visible name.")
        persisted_by_name[name] = tool

    organization_id = conversation_context.conversation.organization_id
    vendor_tools: list[ToolRecord] = []
    seen_names: set[str] = set()
    for spec in run_input.tools:
        if spec.name in seen_names:
            raise ValueError("Run input tools contain a duplicate model-visible name.")
        seen_names.add(spec.name)

        persisted = persisted_by_name.get(spec.name)
        if persisted is not None:
            vendor_tools.append(persisted)
            continue

        vendor_tools.append(
            _FrameworkToolRecord(
                id=_framework_tool_id(spec, organization_id=organization_id),
                llm_config=PlatformTool(
                    name=spec.name,
                    description=spec.description,
                    input_schema=PlatformToolInputSchema.model_validate(
                        spec.input_schema
                    ),
                ),
            )
        )
    return vendor_tools


def _framework_tool_id(spec: ToolSpec, *, organization_id: UUID) -> UUID:
    """Return a stable vendor-facing ID for a framework-only tool."""
    metadata_id = spec.metadata.get("id")
    if metadata_id is not None:
        try:
            return UUID(str(metadata_id))
        except (TypeError, ValueError, AttributeError):
            pass
    return uuid5(
        NAMESPACE_URL,
        f"eylo:framework-tool:{organization_id}:{spec.name}",
    )


class ExistingConversationModel:
    """Framework model adapter over today's LLM vendor adapters."""

    def __init__(
        self,
        conversation_context: object,
        *,
        llm_resolver: LLMConfigResolver,
        model_config_overrides: dict | None = None,
        stream: bool = False,
    ) -> None:
        self._conversation_context = conversation_context
        self._llm_resolver = llm_resolver
        self._model_config_overrides = model_config_overrides or {}
        self._stream = stream

    async def generate(
        self,
        run_input: RunInput,
        settings: ModelSettings,
    ) -> ModelResponse:
        """Resolve org credentials, then call the matching LLM adapter."""
        if (
            settings.provider_config_id is None
            or settings.provider_config_revision is None
        ):
            raise NotConfiguredError(
                capability=Capability.LLM,
                missing=["provider_config", "provider_config_revision"],
                configure_via="/api/agents",
            )
        resolved = await self._llm_resolver.resolve_llm_pinned(
            self.current_context.conversation.organization_id,
            provider_config_id=settings.provider_config_id,
            revision=settings.provider_config_revision,
            overrides=_llm_overrides_from_settings(
                settings,
                self._model_config_overrides,
            ),
        )
        adapter = LLMFactory.from_resolved(resolved).adapter
        messages = _prepare_messages_for_existing_vendor(
            _messages_from_run_input(run_input, self.current_context)
        )
        tools = _vendor_tools_from_run_input(run_input, self.current_context)
        llm_config = resolved.generation.to_storage()
        llm_config["prompt_caching"] = self._model_config_overrides.get(
            "prompt_caching",
            settings.prompt_caching,
        )

        if self._stream:
            llm_response = await self._run_streaming_inference(
                adapter=adapter,
                run_input=run_input,
                messages=messages,
                tools=tools,
                llm_config=llm_config,
                emit_tokens=not has_current_agent_run_budget_scope(),
            )
        else:
            llm_response = await adapter.run_inference(
                messages=messages,
                system_prompt=run_input.instructions,
                tools=tools,
                llm_config=llm_config,
            )
        await _meter_llm_response(llm_response)
        return _model_response_from_llm_response(llm_response)

    async def _run_streaming_inference(
        self,
        *,
        adapter,
        run_input: RunInput,
        messages: list[MessageInDb],
        tools: list,
        llm_config: dict,
        emit_tokens: bool,
    ) -> LLMResponse:
        """Stream through the adapter and deliver ordered voice text segments."""
        turn_id = str(uuid4())
        metadata = _token_metadata(run_input, turn_id)
        text_stream = PlatformTokenStream(run_input=run_input, metadata=metadata)
        emitted_complete = False

        streaming_iter = adapter.run_streaming_inference(
            messages=messages,
            system_prompt=run_input.instructions,
            tools=tools,
            llm_config=llm_config,
        )

        try:
            first_chunk = await streaming_iter.__anext__()
        except (AttributeError, NotImplementedError, StopAsyncIteration, TypeError):
            response = await adapter.run_inference(
                messages=messages,
                system_prompt=run_input.instructions,
                tools=tools,
                llm_config=llm_config,
            )
            if emit_tokens:
                await text_stream.add_response(response)
                await text_stream.flush()
                await _emit_token_complete(run_input, metadata)
            return response

        if not emit_tokens:
            return await _consume_buffered_stream(first_chunk, streaming_iter)

        final_response: LLMResponse | None = None
        for chunk in (first_chunk,):
            final_response, emitted_complete = await _consume_stream_chunk(
                chunk,
                text_stream,
                emitted_complete=emitted_complete,
            )

        async for partial_response in streaming_iter:
            candidate, emitted_complete = await _consume_stream_chunk(
                partial_response,
                text_stream,
                emitted_complete=emitted_complete,
            )
            final_response = candidate or final_response

        if final_response is None:
            raise ValueError("Streaming inference returned no responses")

        if not text_stream.has_received_text:
            await text_stream.add_response(final_response)
        else:
            await text_stream.reconcile_response(final_response)
        await text_stream.flush()
        if not emitted_complete:
            await _emit_token_complete(run_input, metadata)
        return final_response

    @property
    def current_context(self) -> object:
        """Return the latest conversation context for this model call."""
        if isinstance(self._conversation_context, dict):
            return self._conversation_context["conversation_context"]
        return self._conversation_context


class FrameworkConversationRunner:
    """Run one real conversation turn through the primitive framework."""

    def __init__(
        self,
        *,
        conversation_service: ConversationService | None = None,
        context_service: ConversationContextService | None = None,
        message_service: MessageService | None = None,
        tool_executor: ToolExecutor | None = None,
        llm_resolver: LLMConfigResolver | None = None,
        model_factory: Callable[[object, RunConfig], ExistingConversationModel]
        | None = None,
    ) -> None:
        self._conversation_service = conversation_service or ConversationService()
        self._context_service = context_service or ConversationContextService()
        self._message_service = message_service or MessageService()
        self._tool_executor = tool_executor or PlatformToolExecutor()
        self._llm_resolver = llm_resolver
        self._model_factory = model_factory

    async def run(
        self,
        *,
        conversation_id: UUID,
        user_message: MessageInDb,
        config: RunConfig | None = None,
        agent_run_id: UUID | None = None,
        expected_agent_id: UUID | None = None,
        expected_agent_revision: int | None = None,
        durable_context: DurableStepContext | None = None,
    ):
        """Execute and persist one framework-backed conversation turn."""
        if agent_run_id is not None and (
            expected_agent_id is None or expected_agent_revision is None
        ):
            raise ValueError("Durable conversation execution requires an exact agent.")
        if agent_run_id is not None and durable_context is None:
            raise ValueError("Durable conversation execution requires its context.")
        run_config = config or RunConfig()
        conversation = await self._conversation_service.get_(conversation_id)
        context = await self._context_service.build(
            conversation=conversation,
            through_message_id=user_message.id,
        )
        context = _context_through_user_message(context, user_message)
        if agent_run_id is not None:
            _require_exact_context_agent(
                context,
                agent_id=expected_agent_id,
                agent_revision=expected_agent_revision,
            )
        return await self._execute_context(
            context=context,
            user_message=user_message,
            run_config=run_config,
            agent_run_id=agent_run_id,
            last_message_id=user_message.id,
            durable_context=durable_context,
        )

    async def resume(
        self,
        *,
        conversation_id: UUID,
        user_message: MessageInDb,
        wait: AgentRunWaitState,
        config: RunConfig,
        agent_run_id: UUID,
        expected_agent_id: UUID,
        expected_agent_revision: int,
        durable_context: DurableStepContext,
    ):
        """Continue one answered tool interruption on the same product run."""
        conversation = await self._conversation_service.get_(conversation_id)
        context = await self._context_service.build(conversation=conversation)
        _require_exact_context_agent(
            context,
            agent_id=expected_agent_id,
            agent_revision=expected_agent_revision,
        )
        from eylo.common.contracts.tool_availability import ToolRuntimeFact
        from eylo.pipelines.system_tools.availability import (
            refresh_context_tool_availability,
        )

        await refresh_context_tool_availability(
            context,
            runtime_facts={
                ToolRuntimeFact.DURABLE_EXECUTION,
                ToolRuntimeFact.AGENT_RUN,
            },
        )
        agent = agent_spec_from_context(context)
        tool_use_message, tool_call = _resume_tool_call(
            context,
            run_id=agent_run_id,
            wait=wait,
        )
        existing_result = _resume_result_message(
            context,
            run_id=agent_run_id,
            request_id=wait.request_id,
        )
        context.messages = _without_pause_projections(
            context.messages,
            run_id=agent_run_id,
        )
        local_context = {
            "conversation_context": context,
            "last_message_id": (
                existing_result.id
                if existing_result is not None
                else tool_use_message.id
            ),
            "active_user_message": user_message,
            "request_id": user_message.request_id,
            "agent_run_id": agent_run_id,
            "tool_use_messages": {tool_call.id: tool_use_message},
            "durable_context": durable_context,
        }
        run_context = RunContext(
            current_agent=agent,
            handoff_chain=[agent],
            local_context=local_context,
            config=config,
        )
        if existing_result is None:
            tool_result = await self._resume_tool_result(
                run_context=run_context,
                call=tool_call,
                wait=wait,
            )
            tool_result = tool_result.model_copy(
                update={
                    "metadata": tool_result.metadata.model_copy(
                        update={"resume_request_id": str(wait.request_id)}
                    )
                }
            )
            await self._persist_tool_result_message(run_context, tool_call, tool_result)

        refreshed = await self._context_service.build(conversation=conversation)
        refreshed.messages = _without_pause_projections(
            refreshed.messages,
            run_id=agent_run_id,
        )
        return await self._execute_context(
            context=refreshed,
            user_message=user_message,
            run_config=config,
            agent_run_id=agent_run_id,
            last_message_id=local_context["last_message_id"],
            durable_context=durable_context,
        )

    async def _resume_tool_result(
        self,
        *,
        run_context: RunContext,
        call: ToolCall,
        wait: AgentRunWaitState,
    ) -> ToolResult:
        if wait.kind is AgentInputRequestKind.APPROVAL:
            response = wait.response
            if not isinstance(response, dict):
                raise ValueError("Approval response must be an object.")
            decision = response.get("decision")
            if decision == "approve":
                return await self._tool_executor.execute(run_context, call)
            if decision == "reject":
                return ToolResult(
                    tool_call_id=call.id,
                    content="The user rejected this tool action.",
                    is_error=True,
                    metadata={"approval_rejected": True},
                )
            raise ValueError("Approval decision must be approve or reject.")

        return ToolResult(
            tool_call_id=call.id,
            content=json.dumps(
                wait.response, ensure_ascii=False, separators=(",", ":")
            ),
            metadata={
                "human_input_received": True,
                "input_request_id": str(wait.request_id),
            },
        )

    async def _execute_context(
        self,
        *,
        context: object,
        user_message: MessageInDb,
        run_config: RunConfig,
        agent_run_id: UUID | None,
        last_message_id: UUID,
        durable_context: DurableStepContext | None,
    ):
        from eylo.common.contracts.tool_availability import ToolRuntimeFact
        from eylo.pipelines.system_tools.availability import (
            refresh_context_tool_availability,
        )

        execution_facts = (
            {ToolRuntimeFact.DURABLE_EXECUTION, ToolRuntimeFact.AGENT_RUN}
            if agent_run_id is not None and durable_context is not None
            else set()
        )
        await refresh_context_tool_availability(
            context,
            runtime_facts=execution_facts,
        )
        agent = agent_spec_from_context(context)
        base_input = run_input_from_context(context)
        run_input = base_input.model_copy(
            update={
                "metadata": ExistingRunInputMetadata.model_validate(
                    base_input.metadata
                ).model_copy(
                    update={
                        "organization_id": str(context.conversation.organization_id),
                        "request_id": str(user_message.request_id)
                        if user_message.request_id
                        else None,
                    }
                )
            }
        )
        local_context = {
            "conversation_context": context,
            "last_message_id": last_message_id,
            "active_user_message": user_message,
            "request_id": user_message.request_id,
            "agent_run_id": agent_run_id,
            "tool_use_messages": {},
            "durable_context": durable_context,
            "after_model_response": self._persist_model_response_messages,
            "before_tool_call": self._persist_tool_use_message,
            "after_tool_result": self._persist_tool_result_message,
            "after_tool_results": self._refresh_after_tool_results,
        }

        if user_message.request_id is not None:
            await self._transition_request_status(
                user_message.request_id,
                RequestStatus.PROCESSING,
                conversation_id=user_message.conversation_id,
            )
            await get_transaction().commit()

        lifecycle_hooks = FrameworkConversationHooks(
            local_context=local_context,
            user_message=user_message,
        )
        local_context["lifecycle_hooks"] = lifecycle_hooks
        runner = FrameworkRunner(
            self._build_model(local_context, run_config),
            tool_executor=self._tool_executor,
            hooks=lifecycle_hooks,
        )
        try:
            result = await runner.run(
                agent,
                run_input,
                config=run_config,
                local_context=local_context,
            )
        except Exception:
            await _complete_voice_request(
                context=_conversation_context_from_state(local_context),
                user_message=user_message,
            )
            lifecycle_hooks.emit_response_complete(AgentLifecycleOutcome.FAILED)
            raise
        final_context = _conversation_context_from_state(local_context)
        outcome = AgentLifecycleOutcome.COMPLETED

        try:
            final_message = await self._persist_terminal_message(
                result=result,
                context=final_context,
                agent=result.final_agent or agent,
                user_message=user_message,
                parent_message_id=local_context["last_message_id"],
                agent_run_id=agent_run_id,
            )
            if run_config.stream and _should_emit_terminal_message_tokens(result):
                await _emit_terminal_message_tokens(
                    run_input,
                    text=final_message.get_text_content(),
                    turn_id=str(result.run_id),
                )
            elif not run_config.stream:
                from eylo.pipelines.llm.streaming_tts import (
                    push_voice_message_to_tts,
                )

                await push_voice_message_to_tts(
                    final_message,
                    final_context.conversation,
                )
        except Exception:
            outcome = AgentLifecycleOutcome.FAILED
            await self._mark_request_failed_after_terminal_persistence_error(
                user_message
            )
            raise
        finally:
            await _complete_voice_request(
                context=final_context,
                user_message=user_message,
            )
            lifecycle_hooks.emit_response_complete(outcome)
        await self._enqueue_memory_formation(final_context)
        return result.model_copy(update={"final_message_id": final_message.id})

    async def _transition_request_status(
        self,
        request_id: UUID | None,
        requested_status: RequestStatus,
        *,
        conversation_id: UUID,
    ) -> None:
        if request_id is None:
            return
        transition = await self._message_service.update_request_status_by_request_id(
            request_id,
            requested_status,
            conversation_id=conversation_id,
        )
        if not transition.valid:
            logger.error(
                "Request status transition rejected: request_id=%s previous=%s requested=%s",
                request_id,
                transition.previous_status,
                requested_status,
            )
            return

    @staticmethod
    async def _enqueue_memory_formation(conversation_context) -> None:
        """Queue learning only after the complete exchange is durable."""
        primary_agent = getattr(conversation_context, "primary_agent", None)
        if primary_agent is None:
            return
        from eylo.pipelines.memory.formation import enqueue_from_context

        await enqueue_from_context(conversation_context, primary_agent)

    def _build_model(
        self,
        local_context: dict,
        config: RunConfig,
    ) -> ExistingConversationModel:
        if self._model_factory is not None:
            return self._model_factory(local_context, config)
        if self._llm_resolver is None:
            self._llm_resolver = build_llm_config_resolver()
        return ExistingConversationModel(
            local_context,
            llm_resolver=self._llm_resolver,
            model_config_overrides=_model_overrides_from_config(config),
            stream=config.stream,
        )

    async def _mark_request_failed_after_terminal_persistence_error(
        self,
        user_message: MessageInDb,
    ) -> None:
        """Persist a final failed request status without masking the original error."""
        if user_message.request_id is None:
            return

        try:
            transaction = get_transaction()
            await transaction.rollback()
            await self._message_service.update_request_status_by_request_id(
                user_message.request_id,
                RequestStatus.FAILED,
                conversation_id=user_message.conversation_id,
            )
            await transaction.commit()
        except Exception as error:  # noqa: BLE001 - preserve the original terminal error
            logger.error(
                "Failed to mark framework request=%s after terminal persistence "
                "error_type=%s",
                user_message.request_id,
                type(error).__name__,
            )

    async def _persist_model_response_messages(
        self,
        run_context,
        run_input: RunInput,
        response: ModelResponse,
        tool_calls: tuple[ToolCall, ...],
    ) -> None:
        """Prepare ordered model-response persistence for tool execution."""
        if not tool_calls:
            return

        local_context = _local_context_dict(run_context.local_context)
        local_context["pending_model_response"] = response
        local_context["pending_model_response_cursor"] = 0

    async def _persist_tool_use_message(
        self,
        run_context,
        call: ToolCall,
        response: ModelResponse,
    ) -> None:
        """Persist model output blocks in order through this executed tool."""
        local_context = _local_context_dict(run_context.local_context)
        conversation_context = _conversation_context_from_state(local_context)
        parent_message_id = local_context["last_message_id"]
        created_at = arrow.utcnow().datetime
        cursor = int(local_context.get("pending_model_response_cursor", 0))
        stop_index = _model_block_stop_index(response, call, cursor)

        for index in range(cursor, stop_index):
            block = response.blocks[index]
            if block.kind == ModelBlockKind.TEXT:
                text = _model_text_content(block.content)
                if not text:
                    continue
                message = await self._message_service.create_(
                    _primary_agent_message_create(
                        conversation_context,
                        kind=MessageKind.ASSISTANT,
                        content_kind=MessageContentKind.TEXT,
                        content=AssistantMessageContent(
                            content=TextContent(text=text),
                        ),
                        external_id=response.id,
                        meta=_framework_message_meta(response),
                        created_at=created_at + datetime.timedelta(microseconds=index),
                        parent_message_id=parent_message_id,
                        request_id=local_context["request_id"],
                        request_status=RequestStatus.PROCESSING,
                        agent_run_id=local_context["agent_run_id"],
                    )
                )
                parent_message_id = message.id
                continue

            if block.kind != ModelBlockKind.TOOL_CALL:
                continue

            tool_call = ToolCall.model_validate(block.content)
            await self._transition_request_status(
                local_context["request_id"],
                RequestStatus.AWAITING_TOOL_RESULTS,
                conversation_id=conversation_context.conversation.id,
            )
            message = await self._message_service.create_(
                _primary_agent_message_create(
                    conversation_context,
                    kind=MessageKind.TOOL_USE,
                    content_kind=MessageContentKind.TOOL,
                    content=ToolUseMessageContent(
                        content=ToolUseContent(
                            id=tool_call.id,
                            name=tool_call.name,
                            input=tool_call.arguments,
                        )
                    ),
                    external_id=tool_call.id,
                    meta=_framework_message_meta(response),
                    created_at=created_at + datetime.timedelta(microseconds=index),
                    parent_message_id=parent_message_id,
                    request_id=local_context["request_id"],
                    request_status=RequestStatus.AWAITING_TOOL_RESULTS,
                    agent_run_id=local_context["agent_run_id"],
                )
            )
            local_context["tool_use_messages"][tool_call.id] = message
            parent_message_id = message.id

        local_context["pending_model_response_cursor"] = stop_index
        local_context["last_message_id"] = parent_message_id
        local_context["tool_messages_persisted"] = True
        await get_transaction().commit()

    async def _persist_tool_result_message(
        self,
        run_context,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        """Persist a tool result before the framework advances the loop."""
        local_context = _local_context_dict(run_context.local_context)
        tool_use_message = local_context["tool_use_messages"].get(call.id)
        if tool_use_message is None:
            raise ValueError("No persisted TOOL_USE message exists for this tool call.")

        sender_participant_id = _tool_result_sender_participant_id(
            local_context,
            result,
        )
        message = await self._message_service.create_(
            MessageCreate(
                conversation_id=tool_use_message.conversation_id,
                sender_participant_id=sender_participant_id,
                kind=MessageKind.TOOL_RESULT,
                content_kind=MessageContentKind.TOOL,
                content=ToolResultMessageContent(
                    content=[
                        ToolResultContent(
                            tool_use_id=tool_use_message.external_id,
                            name=call.name,
                            content=result.content,
                            is_error=result.is_error,
                        )
                    ],
                ),
                meta=_tool_result_meta(result),
                created_at=arrow.utcnow().datetime,
                parent_message_id=tool_use_message.id,
                request_id=tool_use_message.request_id,
                request_status=RequestStatus.AWAITING_TOOL_RESULTS,
                agent_run_id=local_context["agent_run_id"],
            )
        )
        local_context["last_message_id"] = message.id
        await get_transaction().commit()

    async def _refresh_after_tool_results(
        self,
        run_context,
        run_input: RunInput,
        tool_results: tuple[ToolResult, ...],
    ) -> RunInput:
        """Refresh active conversation state after DB-changing handoff tools."""
        local_context = _local_context_dict(run_context.local_context)
        await self._transition_request_status(
            local_context["request_id"],
            RequestStatus.PROCESSING,
            conversation_id=_conversation_context_from_state(
                local_context
            ).conversation.id,
        )
        await get_transaction().commit()

        if not any(
            result.metadata.get("handoff_context_changed")
            or result.metadata.get("handoff_occurred")
            or result.metadata.get("new_agent_id")
            for result in tool_results
        ):
            return run_input

        current_context = _conversation_context_from_state(local_context)
        active_user_message = local_context.get("active_user_message")
        refreshed = await self._context_service.build(
            conversation=current_context.conversation,
            through_message_id=active_user_message.id
            if isinstance(active_user_message, MessageInDb)
            else None,
        )
        if isinstance(active_user_message, MessageInDb):
            refreshed = _context_through_user_message(refreshed, active_user_message)
        from eylo.common.contracts.tool_availability import ToolRuntimeFact
        from eylo.pipelines.system_tools.availability import (
            refresh_context_tool_availability,
        )

        runtime_facts = set()
        if local_context.get("durable_context") is not None:
            runtime_facts.add(ToolRuntimeFact.DURABLE_EXECUTION)
        if local_context.get("agent_run_id") is not None:
            runtime_facts.add(ToolRuntimeFact.AGENT_RUN)
        await refresh_context_tool_availability(
            refreshed,
            runtime_facts=runtime_facts,
        )
        local_context["conversation_context"] = refreshed

        previous_agent = run_context.current_agent
        next_agent = agent_spec_from_context(refreshed)
        if previous_agent.id != next_agent.id and any(
            result.metadata.get("handoff_occurred") for result in tool_results
        ):
            run_context.record_handoff(next_agent)
            lifecycle_hooks = local_context.get("lifecycle_hooks")
            if isinstance(lifecycle_hooks, FrameworkConversationHooks):
                await lifecycle_hooks.on_handoff(
                    run_context,
                    previous_agent,
                    next_agent,
                )
        else:
            run_context.current_agent = next_agent

        refreshed_input = run_input_from_context(refreshed)
        transient_tool_message_count = int(
            run_input.metadata.get("transient_tool_message_count", 0)
        )
        candidate_transient_tool_messages = (
            run_input.messages[-transient_tool_message_count:]
            if transient_tool_message_count
            else ()
        )
        should_append_transient_tools = _should_append_transient_tool_messages(
            refreshed_input,
            candidate_transient_tool_messages,
            tool_results,
        )
        transient_tool_messages = (
            candidate_transient_tool_messages if should_append_transient_tools else ()
        )

        return refreshed_input.model_copy(
            update={
                "messages": (
                    *refreshed_input.messages,
                    *transient_tool_messages,
                ),
                "metadata": run_input.metadata.model_copy(
                    update=refreshed_input.metadata.model_dump(
                        mode="json",
                        exclude_none=True,
                    )
                ),
            }
        )

    async def _persist_terminal_message(
        self,
        *,
        result,
        context: object,
        agent: AgentSpec,
        user_message: MessageInDb,
        parent_message_id: UUID,
        agent_run_id: UUID | None,
    ) -> MessageInDb:
        request_status = _request_status_for_result(result)
        text = _terminal_text_for_result(result)
        if result.error_message:
            logger.warning(
                "Framework run %s failed with status %s: %s",
                result.run_id,
                result.status.value,
                result.error_message,
            )
        await self._transition_request_status(
            user_message.request_id,
            request_status,
            conversation_id=user_message.conversation_id,
        )
        message = await self._message_service.create_(
            _primary_agent_message_create(
                context,
                kind=MessageKind.ASSISTANT,
                content_kind=MessageContentKind.TEXT,
                content=AssistantMessageContent(
                    content=TextContent(text=text),
                ),
                external_id=str(result.run_id),
                meta=_terminal_message_meta(result, agent),
                created_at=arrow.utcnow().datetime,
                parent_message_id=parent_message_id,
                request_id=user_message.request_id,
                request_status=request_status,
                agent_run_id=agent_run_id,
            )
        )
        if agent_run_id is not None:
            if result.status in _PAUSE_STATUSES:
                kind, prompt, expected_schema, continuation = _agent_run_pause_fields(
                    result
                )
                await pause_agent_run_in_transaction(
                    get_transaction(),
                    organization_id=context.conversation.organization_id,
                    run_id=agent_run_id,
                    kind=kind,
                    prompt=prompt,
                    expected_response_schema=expected_schema,
                    continuation=continuation,
                )
            else:
                lifecycle, outcome, run_result, outcome_reason, failure_summary = (
                    _agent_run_terminal_fields(
                        result,
                        conversation_id=user_message.conversation_id,
                        origin_message_id=user_message.id,
                        final_message_id=message.id,
                    )
                )
                await finish_agent_run_in_transaction(
                    get_transaction(),
                    organization_id=context.conversation.organization_id,
                    run_id=agent_run_id,
                    lifecycle=lifecycle,
                    outcome=outcome,
                    result=run_result,
                    outcome_reason=outcome_reason,
                    failure_summary=failure_summary,
                )
        await get_transaction().commit()
        return message


class FrameworkConversationHooks(RunHooks):
    """Bridge framework lifecycle callbacks to existing agent UI events."""

    def __init__(self, *, local_context: dict, user_message: MessageInDb) -> None:
        self._local_context = local_context
        self._user_message = user_message
        self._agent_started = False
        self._events = AgentLifecycleEmitter()

    async def on_run_end(self, context, result) -> None:
        """Enqueue the agent's attached background agents.

        Once per run, after the loop has finished, so nothing here is on the
        latency path of a reply. Enqueue only — the worker does the model work.
        """
        conversation_context = self.current_context
        # `primary_agent` is the agent record; `get_primary_agent()` returns the
        # participant. Attachments hang off the agent, so it is the former.
        primary_agent = getattr(conversation_context, "primary_agent", None)
        if primary_agent is None:
            return

        await dispatch_background_agents(
            agent_id=primary_agent.id,
            conversation_context=conversation_context,
            request_id=self._local_context.get("request_id"),
        )

    async def on_agent_start(self, context, agent: AgentSpec) -> None:
        if self._agent_started:
            return
        self._agent_started = True
        self._events.emit(
            AgentProcessingEvent,
            context=self.current_context,
            request_id=self._user_message.request_id or self._user_message.id,
            message_id=self._user_message.id,
        )

    async def on_llm_start(self, context, run_input: RunInput) -> None:
        from eylo.pipelines.llm.streaming_tts import (
            prepare_voice_sessions_for_inference,
        )

        conversation = self.current_context.conversation
        await prepare_voice_sessions_for_inference(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            request_id=self._user_message.request_id,
        )
        self._events.emit(
            AgentRunInferenceEvent,
            context=self.current_context,
            request_id=self._user_message.request_id or self._user_message.id,
            message_id=self._user_message.id,
        )

    async def on_tool_start(self, context, call: ToolCall) -> None:
        self._events.emit(
            AgentRunToolEvent,
            context=self.current_context,
            request_id=self._user_message.request_id or self._user_message.id,
            message_id=self._user_message.id,
        )
        await self._file_timeline(
            event_type="agent.tool.started",
            payload={
                "tool_name": call.name,
                "tool_call_id": call.id,
            },
            subject_type="agent.tool",
        )

    async def on_tool_end(
        self,
        context,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        self._events.emit(
            AgentToolResponseEvent,
            context=self.current_context,
            request_id=self._user_message.request_id or self._user_message.id,
            message_id=self._user_message.id,
        )
        await self._file_timeline(
            event_type=(
                "agent.tool.failed" if result.is_error else "agent.tool.completed"
            ),
            payload={
                "tool_name": call.name,
                "tool_call_id": call.id,
            },
            subject_type="agent.tool",
        )

    async def on_handoff(
        self,
        context,
        from_agent: AgentSpec,
        to_agent: AgentSpec,
    ) -> None:
        await self._file_timeline(
            event_type="agent.handoff.completed",
            payload={
                "from_agent_id": str(from_agent.id),
                "to_agent_id": str(to_agent.id),
            },
            subject_type="agent.handoff",
        )

    async def _file_timeline(
        self,
        *,
        event_type: str,
        payload: dict,
        subject_type: str,
    ) -> None:
        user_session_id = self._user_message.user_session_id
        if user_session_id is None:
            return
        conversation = self.current_context.conversation
        raw_run_id = self._local_context.get("agent_run_id")
        subject_id = (
            UUID(str(raw_run_id)) if raw_run_id is not None else self._user_message.id
        )
        await try_file_runtime_fact(
            organization_id=conversation.organization_id,
            user_session_id=user_session_id,
            subject_type=subject_type,
            subject_id=subject_id,
            event_type=event_type,
            payload={
                "agent_run_id": str(raw_run_id) if raw_run_id is not None else None,
                "conversation_id": str(conversation.id),
                **payload,
            },
        )

    def emit_response_complete(self, outcome: AgentLifecycleOutcome) -> None:
        self._events.emit(
            AgentResponseCompleteEvent,
            context=self.current_context,
            request_id=self._user_message.request_id or self._user_message.id,
            message_id=self._user_message.id,
            outcome=outcome,
        )

    @property
    def current_context(self) -> object:
        return _conversation_context_from_state(self._local_context)


def _model_overrides_from_config(config: RunConfig) -> dict:
    return {"prompt_caching": config.prompt_caching}


def _terminal_message_meta(result, agent: AgentSpec) -> dict:
    meta = FrameworkTerminalMessageMeta(
        run_id=str(result.run_id),
        status=result.status,
        model=(
            result.model_responses[-1].model
            if result.model_responses
            else agent.model_settings.model or "unknown"
        ),
        usage=result.usage.model_dump(),
        error=result.error_message is not None,
    ).model_dump(exclude_none=True, mode="json")
    if result.metadata:
        meta[RUN_METADATA_KEY] = result.metadata.model_dump(mode="json")
    for key in (
        APPROVAL_REQUEST_KEY,
        INPUT_REQUEST_KEY,
        CONTINUATION_KEY,
        TERMINAL_RESPONSE_KEY,
        TERMINAL_TOOL_CALL_ID_KEY,
    ):
        if key in result.metadata:
            meta[key] = result.metadata[key]
    return meta


def _primary_agent_message_create(
    context: object,
    *,
    kind: MessageKind,
    content_kind: MessageContentKind,
    content: object,
    external_id: str,
    meta: dict,
    created_at: datetime.datetime,
    parent_message_id: UUID,
    request_id: UUID | None,
    request_status: RequestStatus,
    agent_run_id: UUID | None,
) -> MessageCreate:
    return MessageCreate(
        conversation_id=context.conversation.id,
        sender_participant_id=context.get_primary_agent().id,
        agent_run_id=agent_run_id,
        kind=kind,
        content_kind=content_kind,
        content=content,
        external_id=external_id,
        meta=meta,
        created_at=created_at,
        parent_message_id=parent_message_id,
        request_id=request_id,
        request_status=request_status,
    )


def _require_exact_context_agent(
    context: object,
    *,
    agent_id: UUID | None,
    agent_revision: int | None,
) -> None:
    primary_agent = context.get_primary_agent()
    if (
        primary_agent is None
        or primary_agent.agent_id != agent_id
        or primary_agent.agent_revision != agent_revision
    ):
        raise ValueError(
            "Conversation agent no longer matches the durable run revision."
        )


def _resume_tool_call(
    context: object,
    *,
    run_id: UUID,
    wait: AgentRunWaitState,
) -> tuple[MessageInDb, ToolCall]:
    framework = wait.continuation.get("framework")
    if not isinstance(framework, dict):
        raise ValueError("AgentRun continuation is missing framework state.")
    tool_call_id = framework.get("tool_call_id")
    if not tool_call_id:
        raise ValueError("AgentRun continuation is missing the tool identity.")

    for message in reversed(context.messages):
        if (
            message.agent_run_id != run_id
            or message.kind != MessageKind.TOOL_USE
            or message.external_id != str(tool_call_id)
        ):
            continue
        content = message.get_tool_use_content().content
        return message, ToolCall(
            id=content.id,
            name=content.name,
            arguments=content.input,
        )
    raise ValueError("AgentRun continuation tool call is unavailable.")


def _without_pause_projections(
    messages: list[MessageInDb],
    *,
    run_id: UUID,
) -> list[MessageInDb]:
    return [
        message
        for message in messages
        if not _is_pause_projection(message, run_id=run_id)
    ]


def _resume_result_message(
    context: object,
    *,
    run_id: UUID,
    request_id: UUID,
) -> MessageInDb | None:
    for message in reversed(context.messages):
        if message.agent_run_id != run_id or message.kind != MessageKind.TOOL_RESULT:
            continue
        metadata = _message_meta_dict(message.meta).get("metadata")
        if isinstance(metadata, dict) and metadata.get("resume_request_id") == str(
            request_id
        ):
            return message
    return None


def _is_pause_projection(message: MessageInDb, *, run_id: UUID) -> bool:
    if message.agent_run_id != run_id:
        return False
    meta = _message_meta_dict(message.meta)
    if message.kind == MessageKind.ASSISTANT:
        return meta.get("status") in {
            RunStatus.WAITING_FOR_INPUT.value,
            RunStatus.WAITING_FOR_APPROVAL.value,
        }
    if message.kind != MessageKind.TOOL_RESULT:
        return False
    metadata = meta.get("metadata")
    return isinstance(metadata, dict) and metadata.get("tool_execution_paused") is True


def _message_meta_dict(meta: object) -> dict:
    if isinstance(meta, BaseModel):
        return meta.model_dump(mode="json")
    return dict(meta) if isinstance(meta, dict) else {}


async def _consume_stream_chunk(
    response: LLMResponse,
    text_stream: "PlatformTokenStream",
    *,
    emitted_complete: bool,
) -> tuple[LLMResponse | None, bool]:
    """Route one adapter streaming chunk into the ordered voice stream."""
    if response.metadata.get("streaming", False) and not response.metadata.get(
        "final",
        False,
    ):
        delta = response.metadata.get("delta") or {}
        if delta.get("type") == "text_delta":
            token = delta.get("text") or ""
            await text_stream.add_delta(token)
        return None, emitted_complete

    if not text_stream.has_received_text:
        await text_stream.add_response(response)
    else:
        await text_stream.reconcile_response(response)
    await text_stream.flush()
    if not emitted_complete:
        await _emit_token_complete(text_stream.run_input, text_stream.metadata)
        emitted_complete = True
    return response, emitted_complete


async def _consume_buffered_stream(
    first_response: LLMResponse,
    remaining_responses,
) -> LLMResponse:
    """Buffer budgeted streaming output until final usage is accepted."""
    final_response = _final_stream_response(first_response)
    async for response in remaining_responses:
        final_response = _final_stream_response(response) or final_response
    if final_response is None:
        raise ValueError("Streaming inference returned no final response")
    return final_response


def _final_stream_response(response: LLMResponse) -> LLMResponse | None:
    if response.metadata.get("streaming", False) and not response.metadata.get(
        "final",
        False,
    ):
        return None
    return response


async def _meter_llm_response(response: LLMResponse) -> None:
    usage = response.usage
    await meter_current_agent_run_usage(
        input_tokens=None if usage is None else usage.input_tokens,
        output_tokens=None if usage is None else usage.output_tokens,
    )


def _response_text(response: LLMResponse) -> str:
    """Return the concatenated text blocks from a vendor-normalized response."""
    return "".join(
        _text_from_llm_content(block.content)
        for block in response.content
        if LLMContentType(block.type) == LLMContentType.TEXT
    )


class PlatformTokenStream:
    """Emit vendor streaming deltas as safe Eylo platform text segments."""

    def __init__(self, *, run_input: RunInput, metadata: dict) -> None:
        self.run_input = run_input
        self.metadata = metadata
        self._buffer = SpeakableTextBuffer()
        self._raw_text = ""

    @property
    def has_received_text(self) -> bool:
        return bool(self._raw_text)

    async def add_delta(self, text: str) -> None:
        """Add one raw vendor text delta and emit any completed segments."""
        if not text:
            return
        self._raw_text += text
        await self._emit_segments(self._buffer.add(text))

    async def add_response(self, response: LLMResponse) -> None:
        """Add text from a non-streaming response."""
        await self.add_delta(_response_text(response))

    async def reconcile_response(self, response: LLMResponse) -> None:
        """Append final response text that was not already covered by deltas."""
        final_text = _response_text(response)
        if not final_text or final_text == self._raw_text:
            return
        if final_text.startswith(self._raw_text):
            await self.add_delta(final_text[len(self._raw_text) :])
            return
        if not self._raw_text:
            await self.add_delta(final_text)

    async def flush(self) -> None:
        """Emit any remaining speakable text before the completion signal."""
        await self._emit_segments(self._buffer.flush())

    async def _emit_segments(self, segments: list[str]) -> None:
        for segment in segments:
            await _emit_token(
                self.run_input,
                token=segment,
                is_complete=False,
                metadata=self.metadata,
            )


async def _emit_token_complete(run_input: RunInput, metadata: dict) -> None:
    await _emit_token(run_input, token="", is_complete=True, metadata=metadata)


async def _emit_terminal_message_tokens(
    run_input: RunInput,
    *,
    text: str,
    turn_id: str,
) -> None:
    metadata = _token_metadata(run_input, turn_id)
    if text:
        await _emit_token(
            run_input,
            token=text,
            is_complete=False,
            metadata=metadata,
        )
    await _emit_token_complete(run_input, metadata)


async def _emit_token(
    run_input: RunInput,
    *,
    token: str,
    is_complete: bool,
    metadata: dict,
) -> None:
    """Deliver one ordered text segment to active voice sessions."""
    from eylo.pipelines.llm.streaming_tts import (
        VoiceTextSegment,
        deliver_voice_text_segment,
    )

    organization_id = run_input.metadata.get("organization_id")
    conversation_id = run_input.metadata.get("conversation_id")
    if not organization_id or not conversation_id:
        raise ValueError(
            "Framework streaming requires organization_id and conversation_id."
        )

    await deliver_voice_text_segment(
        VoiceTextSegment(
            organization_id=UUID(str(organization_id)),
            conversation_id=UUID(str(conversation_id)),
            text=token,
            is_complete=is_complete,
            turn_id=metadata.get("turn_id"),
            request_id=metadata.get("request_id"),
        )
    )


def _token_metadata(run_input: RunInput, turn_id: str) -> dict:
    metadata = {"turn_id": turn_id}
    request_id = run_input.metadata.get("request_id")
    if request_id:
        metadata["request_id"] = str(request_id)
    return metadata


def _local_context_dict(local_context: object) -> dict:
    if not isinstance(local_context, dict):
        raise ValueError("Framework conversation callbacks require local context.")
    return local_context


def _request_id_from_input(run_input: RunInput) -> UUID | None:
    request_id = run_input.metadata.get("request_id")
    if not request_id:
        return None
    return UUID(str(request_id))


def _model_text_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        value = content.get("text") or content.get("content") or ""
        return str(value)
    return str(content)


def _model_block_stop_index(
    response: ModelResponse,
    call: ToolCall,
    cursor: int,
) -> int:
    """Return the exclusive block index to persist before executing a tool.

    The framework persists model output lazily so terminal tool results do not
    create dangling future TOOL_USE rows. For the tool about to execute, persist
    all prior text, the matching tool call, and following text until the next
    tool call.
    """
    matched_tool = False
    for index in range(cursor, len(response.blocks)):
        block = response.blocks[index]
        if block.kind != ModelBlockKind.TOOL_CALL:
            continue
        tool_call = ToolCall.model_validate(block.content)
        if matched_tool:
            return index
        if tool_call.id == call.id:
            matched_tool = True

    if matched_tool:
        return len(response.blocks)
    raise ValueError("Tool call identity was not found in its model response.")


def _framework_message_meta(response: ModelResponse) -> dict:
    response_data = response.model_dump()
    return FrameworkMessageMeta(
        llm_response=response_data,
        model_response=response_data,
        **response_data,
    ).model_dump(mode="json")


def _tool_result_meta(result: ToolResult) -> dict:
    metadata = {
        key: value
        for key, value in result.metadata.model_dump(mode="json").items()
        if key != TERMINAL_OUTPUT_KEY
    }
    return FrameworkToolResultMeta(
        tool_call_id=result.tool_call_id,
        is_error=result.is_error,
        metadata=metadata,
    ).model_dump(mode="json")


def _tool_result_sender_participant_id(
    local_context: dict,
    result: ToolResult,
) -> UUID:
    participant_id = result.metadata.get("new_participant_id")
    if participant_id:
        return UUID(str(participant_id))

    conversation_context = _conversation_context_from_state(local_context)
    agent = conversation_context.get_primary_agent()
    if agent is None:
        raise ValueError("ConversationContext has no primary agent participant.")
    return agent.id


def _should_append_transient_tool_messages(
    refreshed_input: RunInput,
    transient_tool_messages: tuple[RunMessage, ...],
    tool_results: tuple[ToolResult, ...],
) -> bool:
    """Append in-memory tool messages only when context rebuild lacks them."""
    expected_tool_call_ids = {
        result.tool_call_id for result in tool_results if result.tool_call_id
    }
    if not expected_tool_call_ids or not transient_tool_messages:
        return False

    refreshed_tool_result_ids = {
        tool_call_id
        for message in refreshed_input.messages
        if (tool_call_id := _tool_result_call_id(message)) is not None
    }
    return not expected_tool_call_ids.issubset(refreshed_tool_result_ids)


def _tool_result_call_id(message: RunMessage) -> str | None:
    tool_result = message.metadata.get("tool_result")
    if isinstance(tool_result, ExistingToolResultMetadata):
        tool_call_id = tool_result.tool_call_id
    elif isinstance(tool_result, dict):
        tool_call_id = tool_result.get("tool_call_id")
    else:
        return None
    return str(tool_call_id) if tool_call_id else None


async def _complete_voice_request(
    *,
    context: object,
    user_message: MessageInDb,
) -> None:
    """Finish voice runtime state directly before emitting a lossy UI delta."""
    from eylo.pipelines.llm.streaming_tts import (
        complete_voice_sessions_for_response,
    )

    conversation = context.conversation
    try:
        await complete_voice_sessions_for_response(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            request_id=user_message.request_id,
        )
    except Exception as error:
        logger.error(
            "Could not finish conversation voice lifecycle error_type=%s",
            type(error).__name__,
        )


def _conversation_context_from_state(local_context: dict) -> object:
    return local_context["conversation_context"]


def _context_through_user_message(context: object, user_message: MessageInDb) -> object:
    messages = getattr(context, "messages", None) or []
    if not isinstance(messages, list):
        return context
    ordered_messages = sorted(
        messages,
        key=lambda message: (message.created_at, str(message.id)),
    )
    for index, message in enumerate(ordered_messages):
        if message.id == user_message.id:
            return context.model_copy(
                update={"messages": ordered_messages[: index + 1]}
            )

    logger.warning(
        "Active user message %s was not present in conversation context %s",
        user_message.id,
        user_message.conversation_id,
    )
    return context


def _llm_overrides_from_settings(
    settings: ModelSettings,
    run_overrides: dict,
) -> dict[str, object]:
    overrides: dict[str, object | None] = {
        "model": run_overrides.get("model", settings.model),
        "max_tokens": run_overrides.get("max_tokens", settings.max_tokens),
        "temperature": run_overrides.get("temperature", settings.temperature),
        "top_k": settings.top_k,
        "top_p": settings.top_p,
        "stop_sequences": settings.stop_sequences,
    }
    return {key: value for key, value in overrides.items() if value is not None}


def _messages_from_run_input(
    run_input: RunInput,
    conversation_context: object,
) -> list[MessageInDb]:
    created_at = arrow.utcnow().datetime
    return [
        _message_from_run_message(
            message,
            conversation_context,
            created_at=created_at + datetime.timedelta(microseconds=index),
        )
        for index, message in enumerate(run_input.messages)
    ]


def _prepare_messages_for_existing_vendor(
    messages: list[MessageInDb],
) -> list[MessageInDb]:
    """Fold framework system context into user messages before vendor transforms.

    Vendor adapters intentionally drop ``MessageKind.SYSTEM`` history entries.
    The framework adapter therefore folds the validated persisted summary into
    the first user message before handing history to those adapters.
    """
    compaction = latest_context_compaction(messages)
    prepared = uncompacted_messages(messages)
    if not prepared:
        return prepared

    first_user_idx = _first_user_index(prepared)
    if first_user_idx is not None and compaction is not None:
        prepared = _replace_message_text(
            prepared,
            first_user_idx,
            _append_context_section(
                prepared[first_user_idx].get_text_content() or "",
                "## Untrusted summary of earlier conversation:",
                compaction.summary.get_text_content() or "",
            ),
        )
    return prepared


def _first_user_index(messages: list[MessageInDb]) -> int | None:
    for index, message in enumerate(messages):
        if message.kind == MessageKind.USER:
            return index
    return None


def _last_user_index(messages: list[MessageInDb]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].kind == MessageKind.USER:
            return index
    return None


def _append_context_section(text: str, heading: str, context: str) -> str:
    if not context:
        return text
    return f"{text}\n\n---\n\n{heading}\n {context}"


def _replace_message_text(
    messages: list[MessageInDb],
    index: int,
    text: str,
) -> list[MessageInDb]:
    updated = list(messages)
    message = updated[index]
    preserved_blocks = []
    if isinstance(message.content, UserMessageContent):
        preserved_blocks = [
            block
            for block in message.content.content
            if not isinstance(block, TextContent)
        ]
    updated[index] = MessageInDb(
        **message.model_dump(exclude={"content"}),
        content=UserMessageContent(content=[TextContent(text=text), *preserved_blocks]),
    )
    return updated


def _message_from_run_message(
    message: RunMessage,
    conversation_context: object,
    *,
    created_at: datetime.datetime,
) -> MessageInDb:
    tool_call = message.metadata.get("tool_call")
    if isinstance(tool_call, dict):
        tool_call = ExistingToolCallMetadata.model_validate(tool_call)
    if isinstance(tool_call, ExistingToolCallMetadata):
        return _tool_use_message_from(
            message, conversation_context, tool_call, created_at
        )

    tool_result = message.metadata.get("tool_result")
    if isinstance(tool_result, dict):
        tool_result = ExistingToolResultMetadata.model_validate(tool_result)
    if isinstance(tool_result, ExistingToolResultMetadata):
        return _tool_result_message_from(
            message,
            conversation_context,
            tool_result,
            created_at,
        )

    kind = _message_kind_from_metadata(message) or _message_kind_from_role(message.role)
    content_kind = _content_kind_from_metadata(message) or MessageContentKind.TEXT
    content = _message_content_for_kind(
        kind,
        message.content,
        content_blocks=_content_blocks_from_metadata(message),
    )
    return _message_indb(
        message,
        conversation_context,
        kind=kind,
        content_kind=content_kind,
        content=content,
        created_at=created_at,
    )


def _tool_use_message_from(
    message: RunMessage,
    conversation_context: object,
    tool_call: ExistingToolCallMetadata,
    created_at: datetime.datetime,
) -> MessageInDb:
    return _message_indb(
        message,
        conversation_context,
        kind=MessageKind.TOOL_USE,
        content_kind=MessageContentKind.TOOL,
        content=ToolUseMessageContent(
            content=ToolUseContent(
                id=tool_call.id,
                name=tool_call.name,
                input=tool_call.arguments,
            ),
        ),
        created_at=created_at,
    )


def _tool_result_message_from(
    message: RunMessage,
    conversation_context: object,
    tool_result: ExistingToolResultMetadata,
    created_at: datetime.datetime,
) -> MessageInDb:
    return _message_indb(
        message,
        conversation_context,
        kind=MessageKind.TOOL_RESULT,
        content_kind=MessageContentKind.TOOL,
        content=ToolResultMessageContent(
            content=[
                ToolResultContent(
                    tool_use_id=tool_result.tool_call_id,
                    name=tool_result.name,
                    content=tool_result.content,
                    is_error=tool_result.is_error,
                )
            ],
        ),
        created_at=created_at,
    )


def _message_indb(
    message: RunMessage,
    conversation_context: object,
    *,
    kind: MessageKind,
    content_kind: MessageContentKind,
    content: object,
    created_at: datetime.datetime,
) -> MessageInDb:
    return MessageInDb(
        id=message.id or uuid4(),
        organization_id=conversation_context.conversation.organization_id,
        conversation_id=conversation_context.conversation.id,
        sender_participant_id=_sender_participant_id(conversation_context, kind),
        kind=kind,
        content_kind=content_kind,
        content=content,
        created_at=created_at,
        updated_at=created_at,
        meta=message.metadata.get("meta") or None,
        request_id=UUID(str(message.metadata["request_id"]))
        if message.metadata.get("request_id")
        else None,
    )


def _sender_participant_id(
    conversation_context: object,
    kind: MessageKind,
) -> UUID:
    if kind == MessageKind.USER:
        contact = conversation_context.get_primary_contact()
        if contact is None:
            raise ValueError("ConversationContext has no primary contact participant.")
        return contact.id

    agent = conversation_context.get_primary_agent()
    if agent is None:
        raise ValueError("ConversationContext has no primary agent participant.")
    return agent.id


def _message_kind_from_role(role: str) -> MessageKind:
    normalized = role.lower()
    if normalized == "user":
        return MessageKind.USER
    if normalized == "system":
        return MessageKind.SYSTEM
    return MessageKind.ASSISTANT


def _message_kind_from_metadata(message: RunMessage) -> MessageKind | None:
    value = message.metadata.get("kind")
    if value is None:
        return None
    if isinstance(value, MessageKind):
        return value
    try:
        return MessageKind(str(value))
    except ValueError:
        return None


def _content_kind_from_metadata(message: RunMessage) -> MessageContentKind | None:
    value = message.metadata.get("content_kind")
    if value is None:
        return None
    if isinstance(value, MessageContentKind):
        return value
    try:
        return MessageContentKind(str(value))
    except ValueError:
        return None


def _message_content_for_kind(
    kind: MessageKind,
    content: str,
    *,
    content_blocks: TextMessageContentBlocks | None = None,
) -> object:
    content_value = content_blocks if content_blocks is not None else content
    if kind == MessageKind.USER:
        return UserMessageContent(content=content_value)
    if kind == MessageKind.SYSTEM:
        return SystemMessageContent(content=content_value)
    return AssistantMessageContent(content=content_value)


def _content_blocks_from_metadata(
    message: RunMessage,
) -> TextMessageContentBlocks | None:
    value = message.metadata.get("content_blocks")
    if value is None:
        return None
    return UserMessageContent(content=value).content


def _model_response_from_llm_response(response: LLMResponse) -> ModelResponse:
    return ModelResponse(
        id=response.id,
        model=response.model,
        blocks=tuple(_model_block_from_llm_block(block) for block in response.content),
        usage=_usage_from_llm_response(response),
        stop_reason=response.stop_reason,
        metadata=response.metadata,
    )


def _model_block_from_llm_block(block: LLMContentBlock) -> ModelOutputBlock:
    content_type = LLMContentType(block.type)
    if content_type == LLMContentType.TEXT:
        return ModelOutputBlock(
            kind=ModelBlockKind.TEXT,
            content=_text_from_llm_content(block.content),
        )
    if content_type == LLMContentType.TOOL_USE:
        return ModelOutputBlock(
            kind=ModelBlockKind.TOOL_CALL,
            content=_tool_call_from_llm_content(block.content),
        )
    return ModelOutputBlock(
        kind=ModelBlockKind.REASONING,
        content=_text_from_llm_content(block.content),
    )


def _text_from_llm_content(content: object) -> str:
    if isinstance(content, LLMTextBlock):
        return content.text
    if isinstance(content, BaseModel):
        content = content.model_dump(mode="json")
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        value = content.get("text") or content.get("content") or ""
        return str(value)
    return str(content)


def _tool_call_from_llm_content(content: object) -> dict:
    if isinstance(content, LLMToolUseBlock):
        return {
            "id": content.id,
            "name": content.name,
            "arguments": content.input,
        }
    if isinstance(content, BaseModel):
        content = content.model_dump(mode="json")
    if isinstance(content, dict):
        return {
            "id": str(content["id"]),
            "name": str(content["name"]),
            "arguments": content.get("input") or content.get("arguments") or {},
        }
    raise ValueError("Tool-use content must be an LLMToolUseBlock or object.")


def _usage_from_llm_response(response: LLMResponse):
    from eylo.framework.agents.model import ModelUsage

    if response.usage is None:
        return ModelUsage()
    return ModelUsage(
        input_tokens=response.usage.input_tokens or 0,
        output_tokens=response.usage.output_tokens or 0,
        cache_creation_input_tokens=response.usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=response.usage.cache_read_input_tokens or 0,
        reasoning_tokens=response.usage.reasoning_tokens or 0,
    )


def _terminal_text_for_result(result) -> str:
    if result.final_output:
        return result.final_output
    if result.is_success:
        return ErrorMessages.EMPTY_RESPONSE
    if result.status == RunStatus.WAITING_FOR_APPROVAL:
        return "I need approval before continuing this request."
    if result.status == RunStatus.WAITING_FOR_INPUT:
        return "I need more information before continuing this request."
    if result.status.value == "timed_out":
        return ErrorMessages.REQUEST_TIMEOUT
    if result.status.value == "max_turns_exceeded":
        return ErrorMessages.MAX_ITERATIONS
    return ErrorMessages.GENERIC_ERROR


def _agent_run_terminal_fields(
    result,
    *,
    conversation_id: UUID,
    origin_message_id: UUID,
    final_message_id: UUID,
) -> tuple[
    AgentRunLifecycle,
    AgentRunOutcome,
    dict | None,
    str | None,
    str | None,
]:
    """Map framework conclusions onto the product's separate lifecycle/outcome."""
    if result.status is RunStatus.COMPLETED:
        return (
            AgentRunLifecycle.COMPLETED,
            AgentRunOutcome.ACHIEVED,
            _conversation_run_result(
                result,
                conversation_id=conversation_id,
                origin_message_id=origin_message_id,
                final_message_id=final_message_id,
            ),
            None,
            None,
        )
    if result.status in {RunStatus.TIMED_OUT, RunStatus.MAX_TURNS_EXCEEDED}:
        reason = f"Conversation execution ended with {result.status.value}."
        return (
            AgentRunLifecycle.COMPLETED,
            AgentRunOutcome.EXHAUSTED,
            _conversation_run_result(
                result,
                conversation_id=conversation_id,
                origin_message_id=origin_message_id,
                final_message_id=final_message_id,
            ),
            reason,
            None,
        )
    return (
        AgentRunLifecycle.FAILED,
        AgentRunOutcome.FAILED,
        None,
        None,
        f"Conversation execution ended with {result.status.value}.",
    )


def _agent_run_pause_fields(
    result,
) -> tuple[AgentInputRequestKind, str, dict, dict]:
    """Project framework interruption metadata onto a typed product request."""
    continuation = result.metadata.get(CONTINUATION_KEY)
    if not isinstance(continuation, dict):
        raise ValueError("Framework pause is missing continuation metadata.")

    if result.status is RunStatus.WAITING_FOR_APPROVAL:
        request = result.metadata.get(APPROVAL_REQUEST_KEY)
        if not isinstance(request, dict):
            raise ValueError("Framework approval pause is missing request metadata.")
        prompt = str(
            request.get("action_summary")
            or request.get("policy_reason")
            or "Approve this agent action?"
        )
        expected_schema = {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["approve", "reject"]},
                "comment": {"type": "string"},
            },
            "required": ["decision"],
            "additionalProperties": False,
        }
        kind = AgentInputRequestKind.APPROVAL
    elif result.status is RunStatus.WAITING_FOR_INPUT:
        request = result.metadata.get(INPUT_REQUEST_KEY)
        if not isinstance(request, dict):
            raise ValueError("Framework input pause is missing request metadata.")
        prompt = str(request.get("prompt") or "Provide the requested information.")
        expected_schema = request.get("expected_input_schema") or {}
        if not isinstance(expected_schema, dict):
            raise ValueError("Framework input response schema must be an object.")
        kind = AgentInputRequestKind.INPUT
    else:
        raise ValueError("Framework result is not an input or approval pause.")

    return (
        kind,
        prompt,
        expected_schema,
        {"framework": continuation, "request": request},
    )


def _conversation_run_result(
    result,
    *,
    conversation_id: UUID,
    origin_message_id: UUID,
    final_message_id: UUID,
) -> dict:
    """Store bounded product references, never a provider response payload."""
    return {
        "kind": "conversation_message",
        "conversation_id": str(conversation_id),
        "origin_message_id": str(origin_message_id),
        "final_message_id": str(final_message_id),
        "framework_run_id": str(result.run_id),
        "framework_status": result.status.value,
        "usage": result.usage.model_dump(mode="json"),
    }


def _request_status_for_result(result) -> RequestStatus:
    if result.is_success:
        return RequestStatus.COMPLETED
    if result.status in _PAUSE_STATUSES:
        return RequestStatus.PROCESSING
    return RequestStatus.FAILED


def _should_emit_terminal_message_tokens(result) -> bool:
    return (
        result.metadata.get("terminal_response") is True
        or result.status in _PAUSE_STATUSES
    )
