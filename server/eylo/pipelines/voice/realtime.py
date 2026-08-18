"""RealtimeManager — session lifecycle and event loop.

Wired into WSSessionState. Called from audio handler:
    handle_audio_config → RealtimeManager(config, queues).initialize()
    handle_audio_data   → manager.send_audio(bytes)
    cleanup             → manager.disconnect()

Hooks
-----
Uses the same ``HookRunner`` + ``RunHooks`` infrastructure as the sync
agent runner so that ``EventBroadcastHooks`` (WebSocket lifecycle
events) and ``RequestStatusHooks`` fire identically.  A session-scoped
``HookContext`` is created once during ``initialize()`` and reused for
all hook calls during the session's lifetime.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import arrow
from pydantic import BaseModel, ConfigDict

from eylo.audio.ops import StreamingResampler
from eylo.common.contracts.voice import VoiceSpeechOutcome
from eylo.common.database import start_transaction
from eylo.modules.agents.hooks.event_broadcast import EventBroadcastHooks
from eylo.modules.agents.hooks.runner import HookRunner
from eylo.modules.agents.hooks.types import HookContext
from eylo.modules.agents.services.tool_execution_utils import (
    ToolDispatchError,
    resolve_model_tool,
)
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.message_content import (
    ToolUseContent,
    ToolUseMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
)
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformToolResult
from eylo.modules.voice_configs.domain import ResolvedRealtime
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.pipelines.conversation.context import ConversationContextService
from eylo.pipelines.voice.lifecycle_policy import matches_end_call_phrase
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceDraft,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.live_transcript import schedule_live_message_transcripts
from eylo.pipelines.voice.realtime_tool_dispatcher import RealtimeToolDispatcher
from eylo.pipelines.voice.tool_executor import without_live_sandbox_tools
from eylo.sockets.realtime.base import RealtimeAdapter
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.events import (
    AudioDataEvent,
    ErrorEvent,
    GoAwayEvent,
    InputTranscriptEvent,
    InterruptionEvent,
    OutputTranscriptEvent,
    RealtimeEvent,
    RealtimeEventType,
    SessionStartedEvent,
    ToolCallEvent,
    TurnCompleteEvent,
    UserSpeechStartedEvent,
)
from eylo.sockets.realtime.factory import RealtimeFactory

logger = logging.getLogger(__name__)

# OutgoingAudioTrack sends at 16kHz. Vendors output 24kHz.
OUTGOING_SAMPLE_RATE = 16000
_VENDOR_SAMPLE_RATE = 24000
_ADAPTER_DISCONNECT_TIMEOUT_SECONDS = 7.0


def _consume_adapter_disconnect_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as error:
        logger.debug(
            "Detached realtime adapter disconnect failed error_type=%s",
            type(error).__name__,
        )


def _consume_teardown_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as error:
        logger.error(
            "Realtime teardown task failed error_type=%s",
            type(error).__name__,
        )


class _ToolInteraction(BaseModel):
    """One tool call → result pair accumulated during a turn."""

    model_config = ConfigDict(frozen=True)

    source_sequence: int
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool
    sender_participant_id: UUID | None
    meta: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RealtimeInteractionCallbacks:
    """Interaction-plane effects driven by normalized realtime events."""

    on_user_activity: Callable[[], None]
    on_processing_started: Callable[[], None]
    on_agent_activity_started: Callable[[], None]
    on_agent_activity_finished: Callable[[], None]
    on_end_call: Callable[[UUID, str | None], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class _PinnedRealtimeVoiceAuthority:
    """Primary Agent voice authority that cannot change during the session."""

    provider_config_id: UUID
    provider_config_revision: int
    vendor: str
    model: str
    voice: str


def _resample_24k_to_16k(audio_24k: bytes, resampler: StreamingResampler) -> bytes:
    """Resample PCM 16-bit mono from 24kHz to 16kHz.

    Both Gemini Live and OpenAI Realtime output 24kHz audio, but
    OutgoingAudioTrack (WebRTC) runs at 16kHz to match the decomposed
    TTS pipeline. Ratio: 2/3 (down=3, up=2).
    """
    return resampler.process(audio_24k)


def _tool_log_fields(tool: ToolInDb | None) -> dict[str, object]:
    """Return stored authority for logs, never the model-provided tool name."""
    if tool is None:
        return {"tool_resolution": "unresolved"}
    return {
        "tool_id": str(tool.id),
        "tool_revision": tool.published_revision,
    }


class RealtimeManager:
    """Orchestrates a realtime voice session.

    Manages the adapter lifecycle, dispatches normalized events, handles
    suppress-audio interruption (D012), buffers live-only turns, and
    fires lifecycle hooks (same ``HookRunner`` used by the sync runner).
    """

    _TOOL_TIMEOUT_SECONDS = 30
    _STUB_TOOL_ID = "stub"
    _STUB_TOOL_NAME = "stub"

    def __init__(
        self,
        config: RealtimeSessionConfig,
        resolved_realtime: ResolvedRealtime,
        tts_response_queue: asyncio.Queue[bytes],
        tts_interrupt_event: asyncio.Event,
        live_buffer: LiveVoiceBuffer,
        interaction: RealtimeInteractionCallbacks,
        end_call_phrases: list[str] | None = None,
        end_call_message: str | None = None,
        on_audio_chunk: Callable[[bytes], None] | None = None,
        hook_runner: HookRunner | None = None,
        on_teardown: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._initial_resolved_realtime: ResolvedRealtime | None = resolved_realtime
        self._pinned_voice_authority = _PinnedRealtimeVoiceAuthority(
            provider_config_id=resolved_realtime.provider_config_id,
            provider_config_revision=resolved_realtime.provider_config_revision,
            vendor=config.vendor,
            model=config.model,
            voice=config.voice,
        )
        self._tts_response_queue = tts_response_queue
        self._tts_interrupt_event = tts_interrupt_event
        self._on_audio_chunk = on_audio_chunk
        self._on_teardown = on_teardown
        self._interaction = interaction
        self._end_call_phrases = list(end_call_phrases or [])
        self._end_call_message = end_call_message
        self._live_buffer = live_buffer
        identity = live_buffer.identity
        if (
            identity.organization_id != config.organization_id
            or identity.conversation_id != config.conversation_id
            or identity.session_id != config.session_id
            or identity.voice_session_id != config.voice_session_row_id
            or identity.runtime_mode is not VoiceRuntimeMode.BROWSER_REALTIME
        ):
            raise ValueError("Realtime voice buffer authority does not match config.")

        self._adapter: RealtimeAdapter | None = None
        self._tool_dispatcher: RealtimeToolDispatcher | None = None
        self._conversation_ctx: ConversationContext | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._tool_tasks: set[asyncio.Task[None]] = set()
        self._callback_tasks: set[asyncio.Task[None]] = set()

        # Participant attribution retained in the live post-call source.
        self._contact_participant_id: UUID | None = None
        self._agent_participant_id: UUID | None = None

        # Transcript accumulation (reset per turn)
        self._input_transcript: str = ""
        self._output_transcript: str = ""
        self._speech_outcome = VoiceSpeechOutcome.DRAINED
        self._current_request_id: UUID | None = None
        self._policy_completion: asyncio.Future[bool] | None = None
        self._speech_request_lock = asyncio.Lock()
        self._response_done = asyncio.Event()
        self._response_done.set()
        self._playback_deadline = 0.0
        self._agent_activity_active = False
        self._end_call_pending = False

        # Tool interaction accumulation (reset per turn)
        self._tool_interactions: list[_ToolInteraction] = []
        self._tool_source_sequence = 0

        # D012: suppress audio between interruption and next TurnComplete.
        self._suppress_audio: bool = False

        self._is_initialized: bool = False
        self._teardown_complete = False
        self._teardown_task: asyncio.Task[None] | None = None
        self._adapter_restart_in_progress = False
        self._event_loop_generation = 0

        # Per-session resampler — never share across sessions.
        self._downsampler = StreamingResampler(
            from_rate=_VENDOR_SAMPLE_RATE, to_rate=OUTGOING_SAMPLE_RATE
        )

        # Hooks — same HookRunner infrastructure as the sync runner.
        if hook_runner is None:
            hook_runner = HookRunner()
            hook_runner.add_run_hooks(EventBroadcastHooks())
            # Learns from the call once it ends; recall happens where the
            # system prompt is built, in ConversationContextService.
            from eylo.pipelines.memory.hooks import MemoryHooks

            hook_runner.add_run_hooks(MemoryHooks())
        self._hooks: HookRunner = hook_runner
        self._hook_ctx: HookContext | None = None
        self._turn_counter: int = 0

        # Dispatch table — maps event types to handler methods
        self._handlers: dict[
            RealtimeEventType, Callable[[RealtimeEvent], Awaitable[None]]
        ] = {
            RealtimeEventType.AUDIO_DATA: self._on_audio_data,
            RealtimeEventType.USER_SPEECH_STARTED: self._on_user_speech_started,
            RealtimeEventType.INPUT_TRANSCRIPT: self._on_input_transcript,
            RealtimeEventType.OUTPUT_TRANSCRIPT: self._on_output_transcript,
            RealtimeEventType.TOOL_CALL: self._on_tool_call,
            RealtimeEventType.INTERRUPTION: self._on_interruption,
            RealtimeEventType.TURN_COMPLETE: self._on_turn_complete,
            RealtimeEventType.GO_AWAY: self._on_go_away,
            RealtimeEventType.ERROR: self._on_error,
            RealtimeEventType.SESSION_STARTED: self._on_session_started,
        }

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    def is_playback_active(self) -> bool:
        """Return whether a response is generating, queued, or still audible."""
        return (
            not self._response_done.is_set()
            or not self._tts_response_queue.empty()
            or time.monotonic() < self._playback_deadline
        )

    async def request_speech(
        self,
        text: str,
        *,
        request_id: UUID,
        wait_until_played: bool,
        timeout_seconds: float,
    ) -> bool:
        """Ask the active vendor to speak one platform-owned policy message."""
        if not text:
            return False

        started_at = time.monotonic()
        async with self._speech_request_lock:
            if not self._adapter or not self._adapter.is_connected:
                raise RuntimeError("Realtime provider is not connected.")
            if not self._response_done.is_set():
                try:
                    async with asyncio.timeout(timeout_seconds):
                        await self._response_done.wait()
                except TimeoutError:
                    logger.warning("Realtime policy speech waited for an active turn.")
                    return False

            self._current_request_id = request_id
            self._policy_completion = asyncio.get_running_loop().create_future()
            self._response_done.clear()
            self._suppress_audio = False
            self._speech_outcome = VoiceSpeechOutcome.DRAINED
            try:
                await self._adapter.request_speech(text)
            except Exception:
                self._response_done.set()
                if not self._policy_completion.done():
                    self._policy_completion.set_result(False)
                raise

            completion = self._policy_completion

        if not wait_until_played:
            return True

        remaining = max(0.0, timeout_seconds - (time.monotonic() - started_at))
        try:
            async with asyncio.timeout(remaining):
                completed = await completion
                if not completed:
                    return False
                await self._wait_for_playback_idle()
                return True
        except TimeoutError:
            logger.warning(
                "Realtime policy speech timed out conversation_id=%s",
                self._config.conversation_id,
            )
            return False

    async def _wait_for_playback_idle(self) -> None:
        while self.is_playback_active():
            await asyncio.sleep(0.02)

    def _mark_agent_activity_started(self) -> None:
        if self._agent_activity_active:
            return
        self._agent_activity_active = True
        self._interaction.on_agent_activity_started()

    def _mark_agent_activity_finished(self) -> None:
        if not self._agent_activity_active:
            return
        self._agent_activity_active = False
        self._interaction.on_agent_activity_finished()

    def _schedule_agent_activity_finished(self) -> None:
        previous = self._tasks.get("playback_activity")
        if previous and not previous.done():
            previous.cancel()

        async def finish_after_playback() -> None:
            await self._wait_for_playback_idle()
            self._mark_agent_activity_finished()

        self._tasks["playback_activity"] = asyncio.create_task(
            finish_after_playback(),
            name="realtime-playback-activity",
        )

    def _schedule_end_call(self, request_id: UUID) -> None:
        task = asyncio.create_task(
            self._interaction.on_end_call(request_id, self._end_call_message),
            name="realtime-end-call",
        )
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)

    def _interrupt_playback(self) -> None:
        while not self._tts_response_queue.empty():
            try:
                self._tts_response_queue.get_nowait()
                self._tts_response_queue.task_done()
            except asyncio.QueueEmpty:
                break
        self._playback_deadline = 0.0
        self._tts_interrupt_event.set()
        self._mark_agent_activity_finished()

    # --- Initialization ---

    async def initialize(self) -> None:
        """Build context, create adapter, connect, start event loop."""
        ctx = await self._build_conversation_context()
        self._conversation_ctx = ctx
        await self._resolve_participants(ctx)

        self._config.system_prompt = ctx.system_prompt or ""
        self._config.tools = list(without_live_sandbox_tools(ctx.get_tools()))
        self._tool_dispatcher = RealtimeToolDispatcher(
            ctx,
            self._live_buffer.identity,
        )

        if self._initial_resolved_realtime is None:
            raise RuntimeError("Realtime provider configuration was already consumed")
        self._adapter = RealtimeFactory.create(
            self._config,
            self._initial_resolved_realtime,
        )
        self._initial_resolved_realtime = None
        await self._adapter.connect()
        try:
            await self._adapter.verify_ready()
        except Exception:
            await self._disconnect_adapter()
            raise
        self._is_initialized = True
        self._start_event_loop()

        logger.info(
            "Realtime session initialized",
            extra={
                "vendor": self._config.vendor,
                "model": self._config.model,
                "conversation_id": str(self._config.conversation_id),
            },
        )

    async def _build_conversation_context(self) -> ConversationContext:
        """Fetch conversation and build context in a read-only transaction."""
        async with start_transaction(ro=True) as db:
            conversation = await ConversationService().get_(
                self._config.conversation_id
            )
            context = await ConversationContextService().build(
                conversation=conversation
            )
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
            return context

    async def _resolve_participants(self, ctx: ConversationContext) -> None:
        """Resolve contact and agent participant IDs for post-call attribution."""
        async with start_transaction(ro=True):
            contact_result = await ConversationParticipantService().get_contact_participant_from_conversation(
                self._config.conversation_id
            )
            if contact_result:
                self._contact_participant_id = contact_result[0].id

        agent_participant = ctx.get_primary_agent()
        if agent_participant:
            self._agent_participant_id = agent_participant.id

    async def _update_agent_context_for_handoff(self) -> None:
        """Change prompt/tools while retaining the primary Agent voice authority."""
        self._assert_pinned_voice_authority()
        if self._conversation_ctx:
            self._config.system_prompt = self._conversation_ctx.system_prompt or ""
            self._config.tools = list(
                without_live_sandbox_tools(self._conversation_ctx.get_tools())
            )

        if self._adapter:
            self._adapter_restart_in_progress = True
            try:
                await self._adapter.update_session(
                    system_prompt=self._config.system_prompt,
                    tools=self._config.tools,
                )
                self._assert_pinned_voice_authority()
                self._start_event_loop()
            finally:
                self._adapter_restart_in_progress = False

    def _assert_pinned_voice_authority(self) -> None:
        current = (
            self._config.vendor,
            self._config.model,
            self._config.voice,
        )
        pinned = (
            self._pinned_voice_authority.vendor,
            self._pinned_voice_authority.model,
            self._pinned_voice_authority.voice,
        )
        if current != pinned:
            raise RuntimeError(
                "A realtime handoff attempted to replace the primary Agent's "
                "pinned Voice Config."
            )

    def _start_event_loop(self) -> None:
        """Start (or restart) the event loop task.

        When called from *inside* the running event loop (e.g. after a
        GoAway reconnect or handoff adapter replacement), the old task is
        cancelled.  The ``CancelledError`` fires at the next ``await`` in
        ``_event_loop``'s ``async for`` — by which time the replacement
        task is already running.
        """
        old = self._tasks.get("event_loop")
        if old and not old.done():
            old.cancel()
        self._event_loop_generation += 1
        generation = self._event_loop_generation
        self._tasks["event_loop"] = asyncio.create_task(
            self._event_loop(generation),
            name=f"realtime-event-loop-{generation}",
        )

    # --- Public API ---

    async def send_audio(self, audio_data: bytes) -> None:
        if self._adapter and self._adapter.is_connected:
            await self._adapter.send_audio(audio_data)

    async def disconnect(self) -> None:
        """Shutdown from an external caller (e.g. WebSocket cleanup).

        Teardown closes the provider transport before cancelling Eylo-owned
        tasks. This lets pending provider reads finish instead of cancelling a
        vendor SDK future while its native transport is still delivering data.
        """
        await self._teardown(notify_owner=False)

    async def _disconnect_adapter(self) -> None:
        adapter = self._adapter
        if adapter is None:
            return

        task = asyncio.create_task(
            adapter.disconnect(),
            name="realtime-adapter-disconnect",
        )
        try:
            done, _ = await asyncio.wait(
                {task},
                timeout=_ADAPTER_DISCONNECT_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            task.add_done_callback(_consume_adapter_disconnect_result)
            raise
        if task not in done:
            task.add_done_callback(_consume_adapter_disconnect_result)
            logger.warning(
                "Realtime adapter disconnect exceeded %.1fs; "
                "provider cleanup continues in background.",
                _ADAPTER_DISCONNECT_TIMEOUT_SECONDS,
            )
            return
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning("Realtime adapter cancelled its disconnect; teardown continues.")
        except Exception as error:
            logger.warning(
                "Realtime adapter disconnect failed error_type=%s; teardown continues.",
                type(error).__name__,
            )

    async def _teardown(
        self,
        speech_outcome: VoiceSpeechOutcome = VoiceSpeechOutcome.CANCELLED,
        *,
        notify_owner: bool,
        reason: str = "realtime_disconnected",
    ) -> None:
        """Run one cancellation-safe teardown and share it across all callers.

        The work lives in its own task. Cancelling a WebSocket handler therefore
        stops that caller without cancelling the provider close underneath it.
        """
        current_task = asyncio.current_task()
        teardown_task = self._teardown_task
        if teardown_task is None:
            teardown_task = asyncio.create_task(
                self._run_teardown(
                    speech_outcome=speech_outcome,
                    notify_owner=notify_owner,
                    reason=reason,
                    initiator_task=current_task,
                ),
                name="realtime-session-teardown",
            )
            teardown_task.add_done_callback(_consume_teardown_result)
            self._teardown_task = teardown_task

        # The owner callback can re-enter through browser cleanup while the
        # teardown task itself is executing. Waiting on itself would deadlock.
        if teardown_task is current_task:
            return
        await asyncio.shield(teardown_task)

    async def _run_teardown(
        self,
        *,
        speech_outcome: VoiceSpeechOutcome,
        notify_owner: bool,
        reason: str,
        initiator_task: asyncio.Task[Any] | None,
    ) -> None:
        """Close the provider, stop owned work, then finalize session state."""
        try:
            # Provider-first is deliberate. Native SDK callbacks may still own
            # pending receive futures until the close handshake has completed.
            await self._disconnect_adapter()

            current_task = asyncio.current_task()
            lifecycle_tasks = [
                task
                for task in (*self._tasks.values(), *self._callback_tasks)
                if task not in {current_task, initiator_task} and not task.done()
            ]
            for task in lifecycle_tasks:
                task.cancel()
            if lifecycle_tasks:
                await asyncio.gather(*lifecycle_tasks, return_exceptions=True)
            self._tasks.clear()
            self._callback_tasks.clear()

            pending_tool_tasks = [
                task
                for task in self._tool_tasks
                if task not in {current_task, initiator_task} and not task.done()
            ]
            if pending_tool_tasks:
                await asyncio.gather(*pending_tool_tasks, return_exceptions=True)
            self._tool_tasks.clear()

            if (
                self._output_transcript
                and self._speech_outcome is VoiceSpeechOutcome.DRAINED
            ):
                self._speech_outcome = speech_outcome
            try:
                await self._buffer_turn(turn_index=self._turn_counter + 1)
            except Exception as error:
                logger.error(
                    "Realtime final turn buffering failed error_type=%s",
                    type(error).__name__,
                )
            self._reset_turn_state()
        finally:
            self._is_initialized = False
            self._response_done.set()
            self._playback_deadline = 0.0
            self._mark_agent_activity_finished()
            if self._policy_completion and not self._policy_completion.done():
                self._policy_completion.set_result(False)
            self._teardown_complete = True

        if notify_owner and self._on_teardown:
            try:
                await self._on_teardown(reason)
            except Exception as error:
                logger.error(
                    "Realtime teardown callback failed error_type=%s",
                    type(error).__name__,
                )

        logger.info(
            "Realtime session disconnected",
            extra={"conversation_id": str(self._config.conversation_id)},
        )

    # --- Event Loop ---

    async def _event_loop(self, generation: int) -> None:
        if not self._adapter:
            return
        logger.info("Realtime event loop started")
        cancelled = False
        try:
            async for event in self._adapter.receive():
                await self._dispatch(event)
        except asyncio.CancelledError:
            cancelled = True
            logger.info("Realtime event loop cancelled")
        except Exception as error:
            logger.error(
                "Realtime event loop failed error_type=%s",
                type(error).__name__,
            )
            await self._teardown(
                VoiceSpeechOutcome.FAILED,
                notify_owner=True,
                reason="realtime_transport_error",
            )
        if (
            not cancelled
            and not self._teardown_complete
            and not self._adapter_restart_in_progress
            and generation == self._event_loop_generation
        ):
            await self._teardown(
                VoiceSpeechOutcome.FAILED,
                notify_owner=True,
                reason="realtime_transport_ended",
            )
        logger.info("Realtime event loop exited")

    async def _dispatch(self, event: RealtimeEvent) -> None:
        handler = self._handlers.get(event.type)
        if handler:
            await handler(event)
        else:
            logger.debug("No handler for event type %s", event.type)

    # --- Handlers ---

    async def _on_audio_data(self, event: AudioDataEvent) -> None:
        """Resample vendor audio (24kHz) to WebRTC output (16kHz) and enqueue."""
        if self._suppress_audio:
            return  # D012: trailing audio from interrupted response
        self._response_done.clear()
        self._mark_agent_activity_started()
        audio = event.audio
        if event.sample_rate != OUTGOING_SAMPLE_RATE:
            audio = _resample_24k_to_16k(audio, self._downsampler)
        if self._on_audio_chunk:
            try:
                self._on_audio_chunk(audio)
            except Exception as error:
                logger.error(
                    "Realtime recording tap failed error_type=%s; call continues.",
                    type(error).__name__,
                )
        bytes_per_second = OUTGOING_SAMPLE_RATE * 2
        playback_start = max(time.monotonic(), self._playback_deadline)
        self._playback_deadline = playback_start + len(audio) / bytes_per_second
        self._tts_response_queue.put_nowait(audio)

    async def _on_input_transcript(self, event: InputTranscriptEvent) -> None:
        """Accumulate user speech transcription from the vendor."""
        if event.text:
            self._response_done.clear()
            self._interaction.on_user_activity()
            if self._current_request_id is None:
                self._current_request_id = uuid4()
            await self._ensure_turn_lifecycle()
        if event.is_final:
            self._input_transcript = event.text
        else:
            self._input_transcript += event.text
        if (
            self._input_transcript
            and event.is_final
            and not self._end_call_pending
            and matches_end_call_phrase(
                self._input_transcript,
                self._end_call_phrases,
            )
        ):
            self._end_call_pending = True
            self._suppress_audio = True
            self._speech_outcome = VoiceSpeechOutcome.INTERRUPTED
            self._interrupt_playback()
            logger.info(
                "Realtime end-call phrase detected conversation_id=%s chars=%d",
                self._config.conversation_id,
                len(self._input_transcript),
            )
        logger.debug(
            "Input transcript update final=%s chars=%d",
            event.is_final,
            len(self._input_transcript),
        )

    async def _on_output_transcript(self, event: OutputTranscriptEvent) -> None:
        """Accumulate model speech transcription from the vendor."""
        if event.text:
            self._response_done.clear()
            self._mark_agent_activity_started()
            if self._current_request_id is None:
                self._current_request_id = uuid4()
            if self._policy_completion is None:
                await self._ensure_turn_lifecycle()
        if event.is_final:
            self._output_transcript = event.text
        else:
            self._output_transcript += event.text
        logger.debug(
            "Output transcript update final=%s chars=%d",
            event.is_final,
            len(self._output_transcript),
        )

    async def _on_tool_call(self, event: ToolCallEvent) -> None:
        """Spawn a background task for tool execution (D014: non-blocking)."""
        logger.info("Realtime tool call received")
        if self._current_request_id is None:
            self._current_request_id = uuid4()
        await self._ensure_turn_lifecycle()
        # D014: execute in background — don't block audio processing
        self._tool_source_sequence += 1
        task = asyncio.create_task(
            self._execute_tool(event, self._tool_source_sequence),
            name=f"realtime-tool-{self._tool_source_sequence}",
        )
        self._tool_tasks.add(task)
        task.add_done_callback(self._tool_tasks.discard)

    async def _on_user_speech_started(self, event: UserSpeechStartedEvent) -> None:
        """Record user activity and interrupt only an active agent response."""
        should_interrupt = self.is_playback_active()
        self._interaction.on_user_activity()
        if should_interrupt:
            self._interrupt_agent_response()

    async def _on_interruption(self, event: InterruptionEvent) -> None:
        """D012: suppress trailing audio and drain playback queue."""
        self._interaction.on_user_activity()
        self._interrupt_agent_response()

    def _interrupt_agent_response(self) -> None:
        """Apply one provider-neutral interruption to generation and playback."""
        self._suppress_audio = True
        self._speech_outcome = VoiceSpeechOutcome.INTERRUPTED
        logger.info("Audio suppressed after interruption")
        self._interrupt_playback()
        if self._policy_completion and not self._policy_completion.done():
            self._policy_completion.set_result(False)

    async def _on_turn_complete(self, event: TurnCompleteEvent) -> None:
        # F01: await pending tool tasks so their results enter the same turn batch.
        if self._tool_tasks:
            await asyncio.gather(*self._tool_tasks, return_exceptions=True)
        request_id = self._current_request_id or uuid4()
        self._current_request_id = request_id
        end_call_pending = self._end_call_pending or matches_end_call_phrase(
            self._input_transcript,
            self._end_call_phrases,
        )
        policy_completion = self._policy_completion
        hook_ctx = self._hook_ctx
        self._turn_counter += 1
        logger.info(
            "Turn complete — input=%d chars, output=%d chars, tools=%d",
            len(self._input_transcript),
            len(self._output_transcript),
            len(self._tool_interactions),
        )
        await self._buffer_turn(turn_index=self._turn_counter)

        # Reset immediately after buffering, before hooks, so disconnect cannot
        # append the same raw turn twice if a hook is cancelled.
        self._reset_turn_state()
        self._suppress_audio = False  # D012: allow audio from the next response
        if self._tool_dispatcher:
            self._tool_dispatcher.reset_turn_state()

        # Fire hooks: on_turn_end + on_agent_end
        # Voice lifecycle events carry a content-free synthetic identity; the
        # raw turn stays in live memory until post-call redaction.
        agent = self._conversation_ctx.primary_agent if self._conversation_ctx else None
        if agent and hook_ctx:
            output_msg = self._make_stub_message(request_id)
            await self._hooks.on_turn_end(hook_ctx, agent, self._turn_counter)
            await self._hooks.on_agent_end(hook_ctx, agent, output_msg)

        self._response_done.set()
        self._schedule_agent_activity_finished()
        if policy_completion and not policy_completion.done():
            policy_completion.set_result(True)
        if end_call_pending:
            self._schedule_end_call(request_id)

    async def _on_go_away(self, event: GoAwayEvent) -> None:
        logger.warning(
            "Vendor GoAway — reconnecting",
            extra={"time_left_ms": event.time_left_ms},
        )
        if self._adapter:
            try:
                await self._adapter.disconnect()
                await self._adapter.connect()
                await self._adapter.verify_ready()
                self._start_event_loop()
            except Exception as error:
                logger.error(
                    "GoAway reconnection failed error_type=%s; terminating session",
                    type(error).__name__,
                )
                # Use _teardown (not disconnect) — we are inside the event
                # loop task so self-cancellation would skip cleanup.
                await self._teardown(
                    VoiceSpeechOutcome.FAILED,
                    notify_owner=True,
                    reason="realtime_reconnect_failed",
                )

    async def _on_error(self, event: ErrorEvent) -> None:
        logger.error(
            "Realtime vendor error",
            extra={
                "code_present": bool(event.code),
                "recoverable": event.is_recoverable,
            },
        )
        if not event.is_recoverable:
            # Fire on_agent_error — re-enables widget input field on fatal errors.
            agent = (
                self._conversation_ctx.primary_agent if self._conversation_ctx else None
            )
            if agent and self._hook_ctx:
                await self._hooks.on_agent_error(
                    self._hook_ctx, agent, RuntimeError("Realtime vendor failed.")
                )
            # Use _teardown (not disconnect) — we are inside the event loop
            # task so self-cancellation would skip cleanup.
            await self._teardown(
                VoiceSpeechOutcome.FAILED,
                notify_owner=True,
                reason="realtime_vendor_error",
            )

    async def _on_session_started(self, event: SessionStartedEvent) -> None:
        """Log vendor session readiness."""
        logger.info(
            "Realtime session ready",
            extra={"vendor_session_id": event.session_id},
        )

    # --- Tool Execution ---

    async def _ensure_turn_lifecycle(self) -> None:
        """Start lifecycle hooks once, when a real conversational turn begins."""
        if self._hook_ctx is not None or self._conversation_ctx is None:
            return
        request_id = self._current_request_id or uuid4()
        self._current_request_id = request_id
        self._hook_ctx = HookContext(
            conversation_context=self._conversation_ctx,
            request_id=request_id,
            user_message=self._make_stub_message(request_id),
        )
        self._interaction.on_processing_started()
        agent = self._conversation_ctx.primary_agent
        if agent:
            await self._hooks.on_agent_start(self._hook_ctx, agent)

    def _make_stub_message(self, request_id: UUID | None = None) -> MessageInDb:
        """Create a minimal MessageInDb for lifecycle event payloads."""
        return MessageInDb(
            id=uuid4(),
            conversation_id=self._config.conversation_id,
            sender_participant_id=self._agent_participant_id or uuid4(),
            kind=MessageKind.TOOL_USE,
            content_kind=MessageContentKind.TOOL,
            content=ToolUseMessageContent(
                content=ToolUseContent(
                    id=self._STUB_TOOL_ID,
                    name=self._STUB_TOOL_NAME,
                    input={},
                )
            ),
            request_id=request_id,
            created_at=arrow.utcnow().datetime,
        )

    def _resolve_tool_by_name(self, tool_name: str) -> ToolInDb | None:
        """Resolve the exact model-visible tool for lifecycle hook attribution.

        Handoff and unknown names intentionally have no ToolInDb hook target.
        """
        if not self._conversation_ctx:
            return None
        try:
            return resolve_model_tool(self._conversation_ctx.get_tools(), tool_name)
        except ToolDispatchError:
            return None

    async def _execute_tool(
        self,
        event: ToolCallEvent,
        source_sequence: int,
    ) -> None:
        if not self._tool_dispatcher:
            return
        agent = self._conversation_ctx.primary_agent if self._conversation_ctx else None
        source_participant = (
            self._conversation_ctx.get_primary_agent()
            if self._conversation_ctx
            else None
        )
        source_participant_id = self._agent_participant_id
        stub_msg = self._make_stub_message()
        tool_db = self._resolve_tool_by_name(event.tool_name)

        # Hook: on_tool_start (skip when tool not found — handoff tools, unknown)
        if agent and tool_db and self._hook_ctx:
            await self._hooks.on_tool_start(
                self._hook_ctx,
                agent,
                tool_db,
                event.arguments,
                stub_msg,
            )

        is_error = False
        try:
            dispatch = await asyncio.wait_for(
                self._tool_dispatcher.execute(
                    tool_call_id=event.tool_call_id,
                    tool_name=event.tool_name,
                    arguments=event.arguments,
                ),
                timeout=self._TOOL_TIMEOUT_SECONDS,
            )
            result = dispatch.result
            is_error = dispatch.is_error
        except asyncio.TimeoutError:
            logger.error(
                "Tool execution timed out",
                extra={
                    **_tool_log_fields(tool_db),
                    "timeout": self._TOOL_TIMEOUT_SECONDS,
                },
            )
            result = "Tool execution timed out"
            is_error = True
            dispatch = None
        except Exception as error:
            logger.error(
                "Tool execution failed",
                extra={
                    **_tool_log_fields(tool_db),
                    "error_type": type(error).__name__,
                },
            )
            result = "Tool execution failed"
            is_error = True
            dispatch = None

        # Hook: on_tool_end (skip when tool not found — handoff tools, unknown)
        if agent and tool_db and self._hook_ctx:
            tool_result = PlatformToolResult(
                tool_use_id=event.tool_call_id,
                content=result,
                is_error=is_error,
            )
            await self._hooks.on_tool_end(
                self._hook_ctx,
                agent,
                tool_db,
                tool_result,
                stub_msg,
            )

        handoff = dispatch.handoff if dispatch else None
        interaction_meta: dict[str, Any] = {}
        if handoff and self._conversation_ctx:
            conversation = self._conversation_ctx.conversation
            interaction_meta = {
                "handoff_outcome": "rejected" if handoff.is_error else "succeeded",
                "swarm_id": str(conversation.swarm_id)
                if conversation.swarm_id
                else None,
                "swarm_revision": conversation.swarm_revision,
                "source_agent_id": str(agent.id) if agent else None,
                "source_agent_revision": source_participant.agent_revision
                if source_participant
                else None,
                "source_participant_id": str(source_participant_id)
                if source_participant_id
                else None,
                "target_agent_id": str(handoff.to_agent.id)
                if handoff.to_agent
                else None,
                "target_agent_revision": handoff.to_participant.agent_revision
                if handoff.to_participant
                else None,
                "target_participant_id": str(handoff.to_participant.id)
                if handoff.to_participant
                else None,
            }

        # Record for ordered live buffering when the turn completes.
        self._tool_interactions.append(
            _ToolInteraction(
                source_sequence=source_sequence,
                tool_call_id=event.tool_call_id,
                tool_name=event.tool_name,
                arguments=event.arguments,
                result=result,
                is_error=is_error,
                sender_participant_id=source_participant_id,
                meta=interaction_meta,
            )
        )

        # F03: after handoff, rebuild context from DB and push only the target
        # Agent's prompt/tools to the existing voice authority. The handoff tool writes the new agent
        # participant to DB; rebuilding reads it back with fresh system_prompt,
        # tools, and handoff_agents — matching the sync runner's _rebuild_context.
        if (
            handoff
            and not handoff.is_error
            and not handoff.circuit_breaker_triggered
            and not handoff.handoff_loop_detected
            and handoff.to_agent
            and self._adapter
            and self._adapter.is_connected
        ):
            from_agent = agent
            to_agent = handoff.to_agent

            # H1: Full context rebuild — fetch fresh context from DB.
            try:
                new_ctx = await self._build_conversation_context()
                self._conversation_ctx = new_ctx

                # Update the tool dispatcher's context so subsequent tool
                # calls use the new agent's tools and system prompt.
                if self._tool_dispatcher:
                    self._tool_dispatcher.update_context(new_ctx)

                # Update hook context with the rebuilt conversation context.
                if self._hook_ctx:
                    self._hook_ctx.update_context(new_ctx)

                # LC-04: re-resolve participant IDs so subsequent messages
                # are attributed to the new agent (not the old one).
                await self._resolve_participants(new_ctx)
            except Exception as error:
                logger.error(
                    "Handoff context rebuild failed error_type=%s; "
                    "using local mutation",
                    type(error).__name__,
                )

            # Hook: on_handoff + on_agent_start for the new agent.
            if from_agent and to_agent and self._hook_ctx:
                await self._hooks.on_handoff(self._hook_ctx, from_agent, to_agent)
                await self._hooks.on_agent_start(self._hook_ctx, to_agent)

            try:
                await self._update_agent_context_for_handoff()
            except Exception as error:
                logger.error(
                    "Handoff realtime session update failed",
                    extra={
                        "agent_id": str(to_agent.id),
                        "error_type": type(error).__name__,
                    },
                )
                if self._hook_ctx:
                    await self._hooks.on_agent_error(self._hook_ctx, to_agent, error)
                await self._teardown(
                    VoiceSpeechOutcome.FAILED,
                    notify_owner=True,
                    reason="realtime_handoff_failed",
                )
                return

        # Guard: only send if adapter is still connected (tool runs in background)
        if self._adapter and self._adapter.is_connected:
            try:
                await self._adapter.send_tool_result(event.tool_call_id, result)
            except Exception as error:
                logger.error(
                    "Failed to send tool result to vendor",
                    extra={
                        **_tool_log_fields(tool_db),
                        "error_type": type(error).__name__,
                    },
                )

    # --- Live-only turn capture ---

    async def _buffer_turn(self, *, turn_index: int) -> bool:
        """Append one logical turn without creating messages or durable facts."""
        is_policy_speech = self._policy_completion is not None
        has_content = (
            self._input_transcript
            or self._output_transcript
            or self._tool_interactions
            or is_policy_speech
        )
        if not has_content:
            return False

        request_id = self._current_request_id or uuid4()
        drafts: list[LiveVoiceDraft] = []
        if self._input_transcript:
            drafts.append(
                LiveVoiceDraft(
                    kind=LiveVoiceItemKind.USER_TRANSCRIPT,
                    payload=self._input_transcript,
                    turn_index=turn_index,
                    participant_id=self._contact_participant_id,
                    request_id=request_id,
                )
            )
        for interaction in sorted(
            self._tool_interactions,
            key=lambda item: item.source_sequence,
        ):
            sender_participant_id = (
                interaction.sender_participant_id or self._agent_participant_id
            )
            drafts.append(
                LiveVoiceDraft(
                    kind=LiveVoiceItemKind.TOOL_CALL,
                    payload=interaction.arguments,
                    turn_index=turn_index,
                    participant_id=sender_participant_id,
                    request_id=request_id,
                    tool_call_id=interaction.tool_call_id,
                    tool_name=interaction.tool_name,
                )
            )
            result_payload: str | dict[str, Any] = interaction.result
            if interaction.meta:
                result_payload = {
                    "content": interaction.result,
                    "handoff": interaction.meta,
                }
            drafts.append(
                LiveVoiceDraft(
                    kind=LiveVoiceItemKind.TOOL_RESULT,
                    payload=result_payload,
                    turn_index=turn_index,
                    participant_id=sender_participant_id,
                    request_id=request_id,
                    tool_call_id=interaction.tool_call_id,
                    tool_name=interaction.tool_name,
                    is_error=interaction.is_error,
                )
            )
        if self._output_transcript and not is_policy_speech:
            drafts.append(
                LiveVoiceDraft(
                    kind=LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
                    payload=self._output_transcript,
                    turn_index=turn_index,
                    participant_id=self._agent_participant_id,
                    request_id=request_id,
                    speech_outcome=self._speech_outcome.value,
                )
            )

        if is_policy_speech:
            self._live_buffer.mark_speech_outcome(
                request_id,
                self._speech_outcome.value,
            )

        if not drafts:
            return is_policy_speech

        try:
            appended = await self._live_buffer.append_turn(drafts)
        except Exception as error:
            logger.error(
                "Realtime raw buffer failed error_type=%s",
                type(error).__name__,
            )
            return False
        if not appended:
            logger.warning("Realtime raw capture is incomplete")
            return False
        schedule_live_message_transcripts(self._live_buffer.identity, appended)
        return True

    def _reset_turn_state(self) -> None:
        self._input_transcript = ""
        self._output_transcript = ""
        self._tool_interactions = []
        self._tool_source_sequence = 0
        self._speech_outcome = VoiceSpeechOutcome.DRAINED
        self._current_request_id = None
        self._hook_ctx = None
        self._policy_completion = None
        self._end_call_pending = False
