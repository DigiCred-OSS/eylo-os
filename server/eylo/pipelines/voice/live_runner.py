"""Session-local decomposed voice turns with no durable raw message origin."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from eylo.common.database import start_transaction
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
from eylo.framework.agents.context import RunInput, RunMessage
from eylo.framework.agents.hooks import RunHooks
from eylo.framework.agents.items import RunItem, RunItemKind
from eylo.framework.agents.model import Model
from eylo.framework.agents.result import RunResult, RunStatus
from eylo.framework.agents.runner import FrameworkRunner
from eylo.framework.agents.tool import ToolCall, ToolExecutor, ToolResult
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageKind,
    MessageMeta,
)
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.voice_transcripts.constants import (
    VoiceRuntimeMode,
    VoiceSpeechOutcome,
)
from eylo.pipelines.conversation.context import ConversationContextService
from eylo.pipelines.conversation.conversation_runner import ExistingConversationModel
from eylo.pipelines.conversation.domain import (
    ExistingRunInputMetadata,
    ExistingRunMessageMetadata,
    ExistingToolCallMetadata,
    ExistingToolResultMetadata,
    agent_spec_from_context,
    run_input_from_context,
)
from eylo.pipelines.llm.streaming_tts import (
    VoiceTextSegment,
    complete_voice_sessions_for_response,
    deliver_voice_text_segment,
    prepare_voice_sessions_for_inference,
)
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceDraft,
    LiveVoiceItem,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.live_transcript import schedule_live_message_transcripts
from eylo.pipelines.voice.request_state import VoiceRequestStatus
from eylo.pipelines.voice.tool_executor import (
    LiveVoiceToolExecutor,
    without_live_sandbox_agent_tools,
)

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.pipelines.websocket.schemas import WSSessionState

logger = logging.getLogger(__name__)

LiveVoiceModelFactory = Callable[[dict[str, Any], RunConfig], Model]


class LiveVoiceLifecycleHooks(RunHooks):
    """Project one decomposed voice turn onto the shared agent lifecycle."""

    def __init__(self, *, local_context: dict[str, Any], request_id: UUID) -> None:
        self._local_context = local_context
        self._request_id = request_id
        self._events = AgentLifecycleEmitter()
        self._started = False
        self._terminal = False

    @property
    def current_context(self) -> ConversationContext:
        return self._local_context["conversation_context"]

    async def on_agent_start(self, context, agent: AgentSpec) -> None:
        if self._started:
            return
        self._started = True
        self._emit(AgentProcessingEvent)

    async def on_llm_start(self, context, run_input: RunInput) -> None:
        conversation = self.current_context.conversation
        await prepare_voice_sessions_for_inference(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            request_id=self._request_id,
        )
        self._emit(AgentRunInferenceEvent)

    async def on_tool_start(self, context, call: ToolCall) -> None:
        self._emit(AgentRunToolEvent)

    async def on_tool_end(
        self,
        context,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        self._emit(AgentToolResponseEvent)

    async def on_run_end(self, context, result: RunResult) -> None:
        successful = result.status in {
            RunStatus.COMPLETED,
            RunStatus.WAITING_FOR_INPUT,
            RunStatus.WAITING_FOR_APPROVAL,
        }
        await self.finish(
            AgentLifecycleOutcome.COMPLETED
            if successful
            else AgentLifecycleOutcome.FAILED
        )

    async def on_error(self, context, error: Exception) -> None:
        await self.finish(AgentLifecycleOutcome.FAILED)

    async def finish(self, outcome: AgentLifecycleOutcome) -> None:
        if self._terminal:
            return
        self._terminal = True
        conversation = self.current_context.conversation
        try:
            await complete_voice_sessions_for_response(
                conversation_id=conversation.id,
                organization_id=conversation.organization_id,
                request_id=self._request_id,
            )
        except Exception as error:
            logger.error(
                "Could not finish decomposed voice lifecycle error_type=%s",
                type(error).__name__,
            )
        finally:
            self._events.emit(
                AgentResponseCompleteEvent,
                context=self.current_context,
                request_id=self._request_id,
                outcome=outcome,
            )

    def _emit(self, event_type) -> None:
        self._events.emit(
            event_type,
            context=self.current_context,
            request_id=self._request_id,
        )


class LiveVoiceTurnRunner:
    """Run decomposed voice turns from live memory, never from raw DB messages."""

    def __init__(
        self,
        live_buffer: LiveVoiceBuffer,
        *,
        session_state: WSSessionState | None = None,
        model_factory: LiveVoiceModelFactory | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        if live_buffer.identity.runtime_mode not in {
            VoiceRuntimeMode.BROWSER_DECOMPOSED,
            VoiceRuntimeMode.TELEPHONY,
        }:
            raise ValueError("The decomposed voice runner cannot own realtime mode.")
        self._buffer = live_buffer
        self._session_state = session_state
        self._model_factory = model_factory
        self._tool_executor = tool_executor or LiveVoiceToolExecutor(
            live_buffer.identity
        )
        self._turn_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()
        self._active_task: asyncio.Task[None] | None = None
        self._active_request_id: UUID | None = None
        self._fallback_messages: list[RunMessage] = []
        self._closed = False

    async def submit(
        self,
        request_id: UUID,
        transcript: str,
        captured_sequence: int | None,
    ) -> bool:
        """Queue one final user utterance without blocking STT or interruption."""
        if self._closed:
            return False

        if captured_sequence is None:
            self._fallback_messages.append(
                _plain_run_message(
                    role="user",
                    content=transcript,
                    kind=MessageKind.USER,
                    request_id=request_id,
                )
            )
        fallback_count = len(self._fallback_messages)
        task = asyncio.create_task(
            self._run_serialized(
                request_id=request_id,
                captured_sequence=captured_sequence,
                fallback_count=fallback_count,
            ),
            name=f"live-voice-turn-{request_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._forget_task)
        return True

    async def interrupt(self) -> None:
        """Cancel only the active inference; queued/new user input remains live."""
        task = self._active_task
        if task is not None and not task.done():
            task.cancel()

    async def drain(self, *, timeout: float = 15.0) -> None:
        """Stop accepting input and settle submitted turns before call teardown."""
        self._closed = True
        tasks = tuple(self._tasks)
        if not tasks:
            return
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*tasks, return_exceptions=True)
        except TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def record_speech_outcome(
        self,
        request_id: str | None,
        outcome: VoiceSpeechOutcome,
    ) -> None:
        """Record whether generated assistant speech drained or was interrupted."""
        if request_id is None:
            return
        try:
            normalized_request_id = UUID(str(request_id))
        except ValueError:
            return
        self._buffer.mark_speech_outcome(
            normalized_request_id,
            outcome.value,
        )
        status = {
            VoiceSpeechOutcome.DRAINED: VoiceRequestStatus.COMPLETED,
            VoiceSpeechOutcome.INTERRUPTED: VoiceRequestStatus.INTERRUPTED,
            VoiceSpeechOutcome.FAILED: VoiceRequestStatus.FAILED,
            VoiceSpeechOutcome.CANCELLED: VoiceRequestStatus.INTERRUPTED,
        }[outcome]
        self._mark_request(normalized_request_id, status)

    async def _run_serialized(
        self,
        *,
        request_id: UUID,
        captured_sequence: int | None,
        fallback_count: int,
    ) -> None:
        try:
            async with self._turn_lock:
                self._active_task = asyncio.current_task()
                self._active_request_id = request_id
                await self._run_turn(
                    request_id=request_id,
                    captured_sequence=captured_sequence,
                    fallback_count=fallback_count,
                )
        except asyncio.CancelledError:
            self._mark_request(request_id, VoiceRequestStatus.INTERRUPTED)
            raise
        except Exception as error:
            self._mark_request(request_id, VoiceRequestStatus.FAILED)
            logger.error(
                "Live voice agent turn failed error_type=%s",
                type(error).__name__,
            )
        finally:
            if self._active_task is asyncio.current_task():
                self._active_task = None
                self._active_request_id = None

    async def _run_turn(
        self,
        *,
        request_id: UUID,
        captured_sequence: int | None,
        fallback_count: int,
    ) -> None:
        identity = self._buffer.identity
        snapshot = await self._buffer.snapshot()
        live_messages = tuple(
            _run_message_from_live_item(item)
            for item in snapshot.items
            if captured_sequence is None or item.sequence <= captured_sequence
        )
        transient_messages = (
            *live_messages,
            *self._fallback_messages[:fallback_count],
        )

        async with start_transaction() as db:
            conversation = await ConversationService(db).get_by_organization_and_id(
                identity.organization_id,
                identity.conversation_id,
            )
            context_service = ConversationContextService(db)
            context = await context_service.build(conversation=conversation)
            from eylo.common.contracts.tool_availability import ToolRuntimeFact
            from eylo.pipelines.system_tools.availability import (
                refresh_context_tool_availability,
            )

            await refresh_context_tool_availability(
                context,
                session=db,
                runtime_facts={
                    ToolRuntimeFact.DURABLE_EXECUTION,
                    ToolRuntimeFact.ACTIVE_VOICE_SESSION,
                },
            )
            agent = without_live_sandbox_agent_tools(agent_spec_from_context(context))
            base_input = run_input_from_context(context)
            run_input = base_input.model_copy(
                update={
                    "messages": (*base_input.messages, *transient_messages),
                    "tools": agent.tools,
                    "metadata": ExistingRunInputMetadata.model_validate(
                        base_input.metadata
                    ).model_copy(
                        update={
                            "organization_id": str(identity.organization_id),
                            "request_id": str(request_id),
                        }
                    ),
                }
            )
            run_config = RunConfig(stream=True)
            local_context: dict[str, Any] = {
                "conversation_context": context,
                "live_voice_identity": identity,
            }

            async def refresh_after_handoff(
                run_context,
                current_input: RunInput,
                tool_results: tuple[ToolResult, ...],
            ) -> RunInput:
                if not any(
                    result.metadata.get("handoff_context_changed")
                    or result.metadata.get("handoff_occurred")
                    for result in tool_results
                ):
                    return current_input
                refreshed = await context_service.build(conversation=conversation)
                await refresh_context_tool_availability(
                    refreshed,
                    session=db,
                    runtime_facts={
                        ToolRuntimeFact.DURABLE_EXECUTION,
                        ToolRuntimeFact.ACTIVE_VOICE_SESSION,
                    },
                )
                local_context["conversation_context"] = refreshed
                next_agent = without_live_sandbox_agent_tools(
                    agent_spec_from_context(refreshed)
                )
                if run_context.current_agent.id != next_agent.id and any(
                    result.metadata.get("handoff_occurred") for result in tool_results
                ):
                    run_context.record_handoff(next_agent)
                else:
                    run_context.current_agent = next_agent
                return current_input.model_copy(
                    update={
                        "instructions": refreshed.system_prompt
                        or next_agent.instructions,
                        "tools": next_agent.tools,
                    }
                )

            local_context["after_tool_results"] = refresh_after_handoff
            model = self._build_model(local_context, run_config, db)
            lifecycle_hooks = LiveVoiceLifecycleHooks(
                local_context=local_context,
                request_id=request_id,
            )
            self._mark_request(request_id, VoiceRequestStatus.LLM_STARTED)
            try:
                result = await FrameworkRunner(
                    model,
                    tool_executor=self._tool_executor,
                    hooks=lifecycle_hooks,
                ).run(
                    agent,
                    run_input,
                    config=run_config,
                    local_context=local_context,
                )
            except asyncio.CancelledError:
                await lifecycle_hooks.finish(AgentLifecycleOutcome.COMPLETED)
                raise
            except Exception:
                await lifecycle_hooks.finish(AgentLifecycleOutcome.FAILED)
                raise

        drafts, response_messages = _response_capture(
            result,
            request_id=request_id,
            context=context,
        )
        if drafts:
            appended = await self._buffer.append_turn(drafts)
            schedule_live_message_transcripts(identity, appended)
            if not appended:
                self._fallback_messages.extend(response_messages)
        if result.status in {
            RunStatus.WAITING_FOR_INPUT,
            RunStatus.WAITING_FOR_APPROVAL,
        }:
            prompt = next(
                (
                    item.message
                    for item in reversed(result.items)
                    if item.kind
                    in {RunItemKind.INPUT_REQUEST, RunItemKind.APPROVAL_REQUEST}
                    and item.message
                ),
                None,
            )
            if prompt:
                await _emit_text(
                    identity.organization_id,
                    identity.conversation_id,
                    request_id,
                    prompt,
                )
        if result.status in {
            RunStatus.COMPLETED,
            RunStatus.WAITING_FOR_INPUT,
            RunStatus.WAITING_FOR_APPROVAL,
        }:
            self._mark_request(request_id, VoiceRequestStatus.LLM_COMPLETED)
        else:
            self._mark_request(request_id, VoiceRequestStatus.FAILED)

    def _build_model(
        self,
        local_context: dict[str, Any],
        config: RunConfig,
        db,
    ) -> Model:
        if self._model_factory is not None:
            return self._model_factory(local_context, config)
        return ExistingConversationModel(
            local_context,
            llm_resolver=build_llm_config_resolver(db),
            stream=config.stream,
        )

    def _mark_request(
        self,
        request_id: UUID,
        status: VoiceRequestStatus,
    ) -> None:
        if self._session_state is not None:
            self._session_state.mark_voice_request(request_id, status)

    def _forget_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Live voice task ended unexpectedly error_type=%s",
                type(error).__name__,
            )


def _run_message_from_live_item(item: LiveVoiceItem) -> RunMessage:
    request_id = item.request_id
    if item.kind is LiveVoiceItemKind.USER_TRANSCRIPT:
        return _plain_run_message(
            role="user",
            content=str(item.payload),
            kind=MessageKind.USER,
            request_id=request_id,
        )
    if item.kind is LiveVoiceItemKind.ASSISTANT_TRANSCRIPT:
        return _plain_run_message(
            role="assistant",
            content=str(item.payload),
            kind=MessageKind.ASSISTANT,
            request_id=request_id,
        )
    if item.kind is LiveVoiceItemKind.DTMF:
        return _plain_run_message(
            role="user",
            content=f"DTMF digits: {item.payload}",
            kind=MessageKind.USER,
            request_id=request_id,
        )
    if item.kind is LiveVoiceItemKind.TOOL_CALL:
        arguments = item.payload if isinstance(item.payload, dict) else {}
        return RunMessage(
            role="assistant",
            content="",
            metadata=ExistingRunMessageMetadata(
                kind=MessageKind.TOOL_USE,
                content_kind=MessageContentKind.TOOL,
                request_id=str(request_id) if request_id else None,
                meta=MessageMeta(),
                tool_call=ExistingToolCallMetadata(
                    id=item.tool_call_id or "unknown",
                    name=item.tool_name or "unknown",
                    arguments=arguments,
                ),
            ),
        )
    return RunMessage(
        role="tool",
        content=_content_text(item.payload),
        metadata=ExistingRunMessageMetadata(
            kind=MessageKind.TOOL_RESULT,
            content_kind=MessageContentKind.TOOL,
            request_id=str(request_id) if request_id else None,
            meta=MessageMeta(),
            tool_result=ExistingToolResultMetadata(
                tool_call_id=item.tool_call_id or "unknown",
                name=item.tool_name,
                is_error=bool(item.is_error),
                content=item.payload,
            ),
        ),
    )


def _plain_run_message(
    *,
    role: str,
    content: str,
    kind: MessageKind,
    request_id: UUID | None,
) -> RunMessage:
    return RunMessage(
        role=role,
        content=content,
        metadata=ExistingRunMessageMetadata(
            kind=kind,
            content_kind=MessageContentKind.TEXT,
            request_id=str(request_id) if request_id else None,
            meta=MessageMeta(),
        ),
    )


def _response_capture(
    result: RunResult,
    *,
    request_id: UUID,
    context: ConversationContext,
) -> tuple[list[LiveVoiceDraft], list[RunMessage]]:
    agent_participant = context.get_primary_agent()
    participant_id = agent_participant.id if agent_participant else None
    drafts: list[LiveVoiceDraft] = []
    messages: list[RunMessage] = []
    tool_names: dict[str, str] = {}
    for item in result.items:
        draft = _draft_from_run_item(
            item,
            request_id=request_id,
            participant_id=participant_id,
            tool_names=tool_names,
        )
        if draft is None:
            continue
        drafts.append(draft)
        messages.append(_run_message_from_draft(draft))
    return drafts, messages


def _draft_from_run_item(
    item: RunItem,
    *,
    request_id: UUID,
    participant_id: UUID | None,
    tool_names: dict[str, str],
) -> LiveVoiceDraft | None:
    if item.kind is RunItemKind.MESSAGE and item.message:
        return LiveVoiceDraft(
            kind=LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
            payload=item.message,
            participant_id=participant_id,
            request_id=request_id,
        )
    if item.kind is RunItemKind.TOOL_CALL:
        call_id = str(item.payload.get("id") or "unknown")
        name = str(item.payload.get("name") or "unknown")
        arguments = item.payload.get("arguments")
        tool_names[call_id] = name
        return LiveVoiceDraft(
            kind=LiveVoiceItemKind.TOOL_CALL,
            payload=arguments if isinstance(arguments, dict) else {},
            participant_id=participant_id,
            request_id=request_id,
            tool_call_id=call_id,
            tool_name=name,
        )
    if item.kind is RunItemKind.TOOL_RESULT:
        call_id = str(item.payload.get("tool_call_id") or "unknown")
        content = item.payload.get("content", "")
        payload = content if isinstance(content, (str, dict)) else {"content": content}
        return LiveVoiceDraft(
            kind=LiveVoiceItemKind.TOOL_RESULT,
            payload=payload,
            participant_id=participant_id,
            request_id=request_id,
            tool_call_id=call_id,
            tool_name=tool_names.get(call_id),
            is_error=bool(item.payload.get("is_error")),
        )
    if item.kind in {RunItemKind.INPUT_REQUEST, RunItemKind.APPROVAL_REQUEST}:
        if item.message:
            return LiveVoiceDraft(
                kind=LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
                payload=item.message,
                participant_id=participant_id,
                request_id=request_id,
            )
    return None


def _run_message_from_draft(draft: LiveVoiceDraft) -> RunMessage:
    item = LiveVoiceItem(
        sequence=0,
        kind=draft.kind,
        payload=draft.payload,
        participant_id=draft.participant_id,
        request_id=draft.request_id,
        tool_call_id=draft.tool_call_id,
        tool_name=draft.tool_name,
        is_error=draft.is_error,
    )
    return _run_message_from_live_item(item)


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    return str(content)


async def _emit_text(
    organization_id: UUID,
    conversation_id: UUID,
    request_id: UUID,
    content: str,
) -> None:
    turn_id = str(uuid4())
    metadata = {"turn_id": turn_id, "request_id": str(request_id)}
    await deliver_voice_text_segment(
        VoiceTextSegment(
            organization_id=organization_id,
            conversation_id=conversation_id,
            text=content,
            is_complete=False,
            turn_id=metadata["turn_id"],
            request_id=metadata["request_id"],
        )
    )
    await deliver_voice_text_segment(
        VoiceTextSegment(
            organization_id=organization_id,
            conversation_id=conversation_id,
            text="",
            is_complete=True,
            turn_id=metadata["turn_id"],
            request_id=metadata["request_id"],
        )
    )


__all__ = ["LiveVoiceTurnRunner"]
