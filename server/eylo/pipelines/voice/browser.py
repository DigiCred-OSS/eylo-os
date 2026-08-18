"""Browser voice pipeline orchestration.

WebSocket handlers receive protocol events, but the runtime voice pipeline owns
STT/TTS setup, transcript session lifecycle, recorder setup, realtime mode, and
voice cleanup. Keeping this here lets browser, WebRTC, and future transports
share pipeline behavior without coupling to a WebSocket handler module.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import arrow
from fastapi import status

from eylo.common.contracts.websocket import build_ws_error_response
from eylo.common.database import start_transaction
from eylo.common.redaction import redact_logs
from eylo.modules.agents.services.llm_readiness import AgentLLMReadinessService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.session_context.schemas import SessionContext
from eylo.modules.voice.schemas.api import (
    CompliancePlan,
    ConversationControl,
    SilenceConfig,
    VoiceConfig,
)
from eylo.modules.voice_configs.catalog import STTProviders, TTSProviders
from eylo.modules.voice_configs.domain import (
    ResolvedRealtime,
    ResolvedSTT,
    ResolvedTTS,
)
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.modules.voice_transcripts.lifecycle import record_voice_session_ended
from eylo.modules.voice_transcripts.schemas.indb import VoiceSessionCreate
from eylo.modules.voice_transcripts.services.indb import VoiceTranscriptService
from eylo.pipelines.session_timeline import try_file_runtime_fact
from eylo.pipelines.voice import consent
from eylo.pipelines.voice.filler import FillerPhraseManager
from eylo.pipelines.voice.interaction_config import apply_voice_interaction_config
from eylo.pipelines.voice.interaction_state import VoiceInteractionState
from eylo.pipelines.voice.lifecycle_policy import (
    browser_voice_session_status,
    should_start_silence_monitor,
)
from eylo.pipelines.voice.lifecycle_policy import (
    monitor_silence as run_silence_monitor,
)
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceBufferIdentity,
)
from eylo.pipelines.voice.live_runner import LiveVoiceTurnRunner
from eylo.pipelines.voice.policy_speech import play_policy_speech
from eylo.pipelines.voice.post_call import finalize_live_voice_history
from eylo.pipelines.voice.provider_runtime import (
    DecomposedVoiceRuntimeIdentity,
    build_stt_runtime_config,
    build_tts_runtime_config,
    resolve_decomposed_voice_runtime,
    resolve_realtime_voice_runtime,
)
from eylo.pipelines.voice.request_state import VoiceRequestSource
from eylo.pipelines.voice.stt import STTRealtime
from eylo.pipelines.voice.transcripts import write_user_transcript
from eylo.pipelines.voice.tts import TTSRealtime
from eylo.pipelines.websocket.errors import not_configured_response
from eylo.pipelines.websocket.schemas import (
    _DEFAULT_SAMPLE_RATE,
    STTEncodingInfo,
    WSSessionState,
    WsEventAction,
    WsRequestEvent,
    WsResponse,
)
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


_LATENCY_METRIC_KEYS = ("first_audio_latency_seconds", "time_to_first_byte_seconds")
_VOICE_PROVIDER_STARTUP_TIMEOUT_SECONDS = 15.0


async def _record_voice_provider_fact(
    session_state: WSSessionState,
    *,
    provider_kind: str,
    state: str,
    vendor: str | None = None,
) -> None:
    await try_file_runtime_fact(
        organization_id=session_state.organization_id,
        user_session_id=session_state.user_session_id,
        subject_type=f"provider.{provider_kind}",
        subject_id=session_state.voice_session_id,
        event_type=f"provider.{provider_kind}.{state}",
        payload={
            "provider_kind": provider_kind,
            **({"vendor": vendor} if vendor else {}),
        },
    )


def _schedule_browser_voice_state(
    session_state: WSSessionState,
    state: VoiceInteractionState,
) -> None:
    """Send one call-scoped state projection without blocking audio callbacks."""
    if (
        session_state.voice_call_id is None
        or session_state.voice_interaction_started_at is None
    ):
        return
    session_state.voice_interaction_sequence += 1
    payload = {
        "voice_call_id": session_state.voice_call_id,
        "call_started_at": session_state.voice_interaction_started_at,
        "sequence": session_state.voice_interaction_sequence,
        "state": state.value,
    }
    task = asyncio.create_task(
        S_ws_manager.send_response(
            {"kind": WsEventAction.VOICE_STATE, "data": payload},
            session_state.organization_id,
            session_state.session_id,
        ),
        name=f"voice-state-{session_state.voice_interaction_sequence}",
    )
    task.add_done_callback(_consume_voice_state_result)


def _consume_voice_state_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.debug("Voice interaction state delivery was cancelled.")
    except Exception as error:
        logger.error(
            "Voice interaction state delivery failed error_type=%s",
            type(error).__name__,
        )


def _mark_browser_awaiting_user(session_state: WSSessionState) -> None:
    """Start caller-silence timing only when no agent work remains audible."""
    if (
        session_state.is_agent_thinking
        or session_state.transport_playback_gate.is_active
    ):
        return
    already_awaiting = session_state.voice_activity_gate.is_awaiting_user
    session_state.voice_activity_gate.mark_agent_activity_finished()
    if not already_awaiting and session_state.voice_interaction_callback:
        session_state.voice_interaction_callback(VoiceInteractionState.LISTENING)


def _mark_browser_output_started(session_state: WSSessionState) -> None:
    was_audible = session_state.transport_playback_gate.is_active
    session_state.transport_playback_gate.mark_started()
    session_state.voice_activity_gate.mark_agent_activity_started()
    if not was_audible and session_state.voice_interaction_callback:
        session_state.voice_interaction_callback(VoiceInteractionState.SPEAKING)


def _mark_browser_output_producer_finished(session_state: WSSessionState) -> None:
    session_state.transport_playback_gate.mark_producer_finished()


def _cancel_browser_output(session_state: WSSessionState) -> None:
    session_state.transport_playback_gate.cancel()


def _collect_audio_metrics(session_state: WSSessionState) -> dict[str, Any]:
    """Vendor metrics for this session, subject to the agent's ObservabilityPlan.

    Returning `{}` when metrics are disabled is what makes the switch real:
    the session-ended event then carries no metrics, and the teardown logs
    have nothing to print.
    """
    if not session_state.metrics_enabled:
        return {}

    metrics: dict[str, Any] = {}
    if session_state.stt_socket:
        metrics["stt"] = session_state.stt_socket.metrics
    if session_state.tts_socket:
        metrics["tts"] = session_state.tts_socket.metrics_snapshot().model_dump()

    if not session_state.vendor_latency_tracking_enabled:
        for vendor_metrics in metrics.values():
            if isinstance(vendor_metrics, dict):
                for key in _LATENCY_METRIC_KEYS:
                    vendor_metrics.pop(key, None)
    return metrics


async def _run_voice_cleanup_step(
    organization_id: UUID,
    step: str,
    operation: Awaitable[Any],
) -> None:
    """Contain secondary cleanup failures so terminal persistence still runs."""
    try:
        await operation
    except Exception as error:
        logger.error(
            "Browser voice cleanup failed organization_id=%s step=%s error_type=%s",
            organization_id,
            step,
            type(error).__name__,
        )


async def _send_realtime_ready_signals(
    ctx: SessionContext,
    vendor: str,
) -> None:
    payload = {
        "message": "Realtime vendor handles STT+TTS",
        "vendor": vendor,
        "runtime_mode": VoiceRuntimeMode.BROWSER_REALTIME.value,
        "timestamp": arrow.utcnow().timestamp(),
    }
    try:
        await S_ws_manager.send_response(
            {"kind": WsEventAction.STT_READY, "data": payload},
            ctx.ws.organization_id,
            ctx.ws.session_id,
        )
        await S_ws_manager.send_response(
            {"kind": WsEventAction.TTS_READY, "data": payload},
            ctx.ws.organization_id,
            ctx.ws.session_id,
        )
        logger.info("Sent stt:ready and tts:ready signals for realtime mode")
    except Exception as error:
        logger.error(
            "Realtime ready signal failed error_type=%s",
            type(error).__name__,
        )


def _get_browser_tts_audio_metadata(
    voice_config: VoiceConfig | None,
    tts_config: dict[str, Any] | None = None,
) -> tuple[int, str]:
    if voice_config and voice_config.realtime_provider_config_id:
        return 16000, "pcm_s16le"

    if tts_config is None:
        return 16000, "pcm_s16le"
    voice_provider_dump = tts_config

    vendor = voice_provider_dump.get("vendor")
    output_format = voice_provider_dump.get("output_format") or {}
    if isinstance(output_format, str):
        if output_format.startswith("pcm_"):
            _, sample_rate = output_format.split("_", 1)
            if sample_rate.isdigit():
                return int(sample_rate), "pcm_s16le"
    if isinstance(output_format, dict):
        sample_rate = output_format.get("sample_rate")
        encoding = output_format.get("encoding")
        if isinstance(sample_rate, int):
            return sample_rate, str(encoding or "pcm_s16le")

    vendor_defaults: dict[str, tuple[int, str]] = {
        "cartesia": (16000, "pcm_s16le"),
        "elevenlabs": (16000, "pcm_s16le"),
        "sarvam": (
            int(voice_provider_dump.get("speech_sample_rate") or 16000),
            "pcm_s16le",
        ),
    }
    return vendor_defaults.get(vendor, (16000, "pcm_s16le"))


def _compliance_plan(voice_config: VoiceConfig | None) -> CompliancePlan:
    """The agent's CompliancePlan, or schema defaults when unconfigured."""
    return voice_config.compliance if voice_config else CompliancePlan()


def _compliance_meta(voice_config: VoiceConfig | None) -> dict:
    """Compliance decisions post-call projection needs, as content-free meta."""
    plan = _compliance_plan(voice_config)
    return {
        "store_raw_vendor_payloads": plan.store_raw_vendor_payloads,
        "allow_sensitive_metadata": plan.allow_sensitive_metadata,
        "redact_pii_in_transcripts": plan.redact_pii_in_transcripts,
        "recording_consent_required": plan.recording_consent_required,
    }


def _artifact_plan(voice_config: VoiceConfig | None):
    """The agent's ArtifactPlan, or schema defaults when unconfigured.

    Attribute access is direct rather than `getattr(..., default)`: the field
    is `artifacts`, and a defensive getattr on the wrong name silently
    returned defaults, so both storage gates read nothing.
    """
    from eylo.modules.voice.schemas.api import ArtifactPlan

    return voice_config.artifacts if voice_config else ArtifactPlan()


async def _start_browser_voice_session(
    session_state: WSSessionState,
    conversation_id: UUID,
    voice_config: VoiceConfig | None,
    *,
    contact_id: UUID,
    contact_participant_id: UUID,
    agent_participant_id: UUID,
    voice_call_id: str | None = None,
    resolved_realtime: ResolvedRealtime | None = None,
    decomposed_identity: DecomposedVoiceRuntimeIdentity | None = None,
) -> UUID:
    if (
        session_state.voice_transcript_session_started
        or session_state.voice_session_id is not None
        or session_state.live_voice_buffer is not None
    ):
        raise RuntimeError("A browser voice call is already active on this session.")

    voice_call_id = voice_call_id or str(uuid4())
    session_state.voice_activity_gate.reset()
    session_state.transport_playback_gate.reset()
    session_state.speech_activity_event.clear()
    session_state.tts_interrupt_event.clear()
    session_state.voice_requests.clear()
    session_state.current_voice_request_id = None
    session_state.voice_termination_task = None
    session_state.voice_termination_complete = False
    session_state.voice_termination_reason = None
    session_state.voice_terminal_callback = None
    runtime_mode = (
        VoiceRuntimeMode.BROWSER_REALTIME
        if voice_config and voice_config.realtime_provider_config_id
        else VoiceRuntimeMode.BROWSER_DECOMPOSED
    )
    canonical_storage_requested = _artifact_plan(
        voice_config
    ).transcript_storage_enabled
    realtime_vendor = realtime_model = None
    if resolved_realtime is not None:
        realtime_vendor = resolved_realtime.provider.value
        realtime_model = str(resolved_realtime.config["model"])

    async with start_transaction():
        voice_session = await VoiceTranscriptService().start_session(
            VoiceSessionCreate(
                organization_id=session_state.organization_id,
                conversation_id=conversation_id,
                user_session_id=session_state.user_session_id,
                session_id=voice_call_id,
                runtime_mode=runtime_mode,
                transport="webrtc",
                agent_id=session_state.agent_id,
                agent_revision=session_state.agent_revision,
                started_at=arrow.utcnow().datetime,
                stt_vendor=(
                    decomposed_identity.stt_vendor if decomposed_identity else None
                ),
                stt_model=(
                    decomposed_identity.stt_model if decomposed_identity else None
                ),
                tts_vendor=(
                    decomposed_identity.tts_vendor if decomposed_identity else None
                ),
                tts_model=(
                    decomposed_identity.tts_model if decomposed_identity else None
                ),
                tts_voice=(
                    decomposed_identity.tts_voice if decomposed_identity else None
                ),
                realtime_vendor=realtime_vendor,
                realtime_model=realtime_model,
                recording_enabled=session_state.audio_recorder is not None,
                audio_format="wav",
                # Carried on content-free session state for post-call processing.
                meta={
                    **_compliance_meta(voice_config),
                    "canonical_storage_requested": canonical_storage_requested,
                },
            )
        )
    session_state.voice_session_id = voice_session.id
    session_state.voice_call_id = voice_call_id
    session_state.voice_interaction_sequence = 0
    session_state.voice_interaction_started_at = arrow.utcnow().timestamp()
    session_state.voice_interaction_callback = partial(
        _schedule_browser_voice_state,
        session_state,
    )
    session_state.voice_output_drained_callback = partial(
        _mark_browser_awaiting_user,
        session_state,
    )
    session_state.live_voice_buffer = LiveVoiceBuffer(
        LiveVoiceBufferIdentity(
            organization_id=session_state.organization_id,
            conversation_id=conversation_id,
            session_id=voice_call_id,
            voice_session_id=voice_session.id,
            runtime_mode=runtime_mode,
            canonical_storage_requested=canonical_storage_requested,
            contact_id=contact_id,
            contact_participant_id=contact_participant_id,
            agent_participant_id=agent_participant_id,
        )
    )
    session_state.is_voice_mode = True
    session_state.voice_transcript_session_started = True
    session_state.voice_transcript_runtime_mode = runtime_mode.value
    if session_state.audio_recorder is not None:
        session_state.audio_recorder.bind_voice_session(
            voice_session_id=voice_session.id,
            telephony_call_id=None,
        )
    return voice_session.id


def _maybe_initialize_recorder(
    session_state: WSSessionState,
    conversation_id: UUID,
    voice_config: VoiceConfig | None,
    tts_config: dict[str, Any] | None = None,
    *,
    recording_session_id: str | None = None,
) -> None:
    from eylo.common.config import settings

    if not settings.ENABLE_VOICE_RECORDING:
        return
    if not _artifact_plan(voice_config).audio_storage_enabled:
        # The deployment allows recording, but this agent's ArtifactPlan does
        # not. Both must agree: the setting is a deployment kill switch, the
        # config is the operator's per-agent choice.
        return
    if session_state.audio_recorder is not None:
        return

    def build() -> None:
        _build_recorder(
            session_state,
            conversation_id,
            voice_config,
            tts_config=tts_config,
            recording_session_id=recording_session_id,
        )

    try:
        build()
    except Exception as error:
        logger.error(
            "Voice recorder initialization failed organization_id=%s "
            "error_type=%s; call continues.",
            session_state.organization_id,
            type(error).__name__,
        )
        return
    if _compliance_plan(voice_config).recording_consent_required:
        # Notification is attempted before the greeting, but it is not a data
        # control and cannot interrupt the primary recording flow.
        session_state.recording_consent_state = "pending"
        return

    session_state.recording_consent_state = "not_required"


def _build_recorder(
    session_state: WSSessionState,
    conversation_id: UUID,
    voice_config: VoiceConfig | None,
    *,
    tts_config: dict[str, Any] | None = None,
    recording_session_id: str | None = None,
) -> None:
    from eylo.pipelines.voice.recording import AudioRecorder

    agent_sample_rate, agent_encoding = _get_browser_tts_audio_metadata(
        voice_config,
        tts_config,
    )

    session_state.audio_recorder = AudioRecorder(
        organization_id=session_state.organization_id,
        conversation_id=conversation_id,
        session_id=recording_session_id or session_state.session_id,
        storage_provider_config_id=(
            voice_config.storage_provider_config_id if voice_config else None
        ),
        storage_provider_config_revision=(
            voice_config.storage_provider_config_revision if voice_config else None
        ),
        user_sample_rate=session_state.stt_encoding_info.sample_rate,
        agent_sample_rate=agent_sample_rate,
        user_encoding=session_state.stt_encoding_info.encoding,
        agent_encoding=agent_encoding,
    )
    logger.info(
        "Voice recorder initialized organization_id=%s (user=%dHz, agent=%dHz)",
        session_state.organization_id,
        session_state.stt_encoding_info.sample_rate,
        agent_sample_rate,
    )


async def cleanup_audio_services(ctx: SessionContext) -> None:
    from eylo.runtime.tasks import teardown_long_running_tasks, teardown_queues

    if not ctx.ws:
        return
    was_realtime_mode = ctx.ws.realtime_mode
    try:
        audio_metrics = _collect_audio_metrics(ctx.ws)
    except Exception as error:
        audio_metrics = {}
        logger.error(
            "Browser voice metrics collection failed organization_id=%s error_type=%s",
            ctx.organization_id,
            type(error).__name__,
        )
    ended_reason = ctx.ws.voice_termination_reason or "voice_cleanup_without_reason"
    audio_metrics["termination_reason"] = ended_reason
    voice_transcript_session_started = ctx.ws.voice_transcript_session_started
    voice_session_id = ctx.ws.voice_session_id
    voice_transcript_runtime_mode = ctx.ws.voice_transcript_runtime_mode
    if ctx.ws.live_voice_buffer is not None:
        try:
            FillerPhraseManager.cancel_filler(
                ctx.ws.live_voice_buffer.identity.conversation_id
            )
        except Exception as error:
            logger.error(
                "Browser filler cleanup failed organization_id=%s error_type=%s",
                ctx.organization_id,
                type(error).__name__,
            )
    ctx.ws.is_agent_thinking = False

    await _run_voice_cleanup_step(
        ctx.organization_id,
        "policy_tasks",
        teardown_long_running_tasks(ctx.ws.voice_policy_tasks),
    )
    ctx.ws.voice_policy_tasks.clear()

    realtime_manager = ctx.ws.realtime_manager
    if realtime_manager:
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "realtime",
            realtime_manager.disconnect(),
        )
        logger.info(
            "Realtime services cleaned up organization_id=%s",
            ctx.organization_id,
        )
        await _record_voice_provider_fact(
            ctx.ws,
            provider_kind="realtime",
            state="disconnected",
        )
    ctx.ws.realtime_manager = None

    if was_realtime_mode:
        ctx.ws.realtime_mode = False
        if ctx.ws.tts_response_queue is not None:
            while not ctx.ws.tts_response_queue.empty():
                try:
                    ctx.ws.tts_response_queue.get_nowait()
                    ctx.ws.tts_response_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            ctx.ws.tts_response_queue = None

    if ctx.ws.stt_started:
        if ctx.ws.stt_socket:
            await _run_voice_cleanup_step(
                ctx.organization_id,
                "stt_socket",
                ctx.ws.stt_socket.disconnect(),
            )
        stt_queues_to_tear_down = [
            q for q in [ctx.ws.stt_response_queue, ctx.ws.stt_request_queue] if q
        ]
        if stt_queues_to_tear_down:
            await _run_voice_cleanup_step(
                ctx.organization_id,
                "stt_queues",
                teardown_queues(stt_queues_to_tear_down, join_timeout=5),
            )
        logger.info(
            "STT services cleaned up organization_id=%s metrics=%s",
            ctx.organization_id,
            audio_metrics.get("stt", {}),
        )
        await _record_voice_provider_fact(
            ctx.ws,
            provider_kind="stt",
            state="disconnected",
        )
    ctx.ws.stt_started = False
    ctx.ws.stt_socket = None
    ctx.ws.stt_response_queue = None
    ctx.ws.stt_request_queue = None
    await _run_voice_cleanup_step(
        ctx.organization_id,
        "stt_tasks",
        teardown_long_running_tasks(ctx.ws.stt_session_tasks),
    )
    ctx.ws.stt_session_tasks.clear()

    if ctx.ws.live_voice_turn_runner is not None:
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "live_turns",
            ctx.ws.live_voice_turn_runner.drain(),
        )
        ctx.ws.live_voice_turn_runner = None

    if ctx.ws.tts_manager or ctx.ws.tts_started:
        tts_queues_to_tear_down = [
            q for q in [ctx.ws.tts_response_queue, ctx.ws.tts_request_queue] if q
        ]
        if tts_queues_to_tear_down:
            await _run_voice_cleanup_step(
                ctx.organization_id,
                "tts_queues",
                teardown_queues(tts_queues_to_tear_down, join_timeout=5),
            )
        if ctx.ws.tts_socket:
            await _run_voice_cleanup_step(
                ctx.organization_id,
                "tts_socket",
                ctx.ws.tts_socket.disconnect(),
            )
        logger.info(
            "TTS services cleaned up organization_id=%s metrics=%s",
            ctx.organization_id,
            audio_metrics.get("tts", {}),
        )
        await _record_voice_provider_fact(
            ctx.ws,
            provider_kind="tts",
            state="disconnected",
        )
    ctx.ws.tts_started = False
    ctx.ws.tts_socket = None
    ctx.ws.tts_manager = None
    ctx.ws.tts_response_queue = None
    ctx.ws.tts_request_queue = None
    await _run_voice_cleanup_step(
        ctx.organization_id,
        "tts_tasks",
        teardown_long_running_tasks(ctx.ws.tts_session_tasks),
    )
    ctx.ws.tts_session_tasks.clear()

    if ctx.ws.audio_recorder:
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "recorder",
            ctx.ws.audio_recorder.finalize(),
        )
        ctx.ws.audio_recorder = None

    ended_at = arrow.utcnow().datetime
    if ctx.ws.live_voice_buffer is not None:
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "canonical_history",
            finalize_live_voice_history(ctx.ws.live_voice_buffer),
        )

    if voice_transcript_session_started and voice_session_id is not None:
        runtime_mode = (
            VoiceRuntimeMode(voice_transcript_runtime_mode)
            if voice_transcript_runtime_mode
            else (
                VoiceRuntimeMode.BROWSER_REALTIME
                if was_realtime_mode
                else VoiceRuntimeMode.BROWSER_DECOMPOSED
            )
        )
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "session_completion",
            record_voice_session_ended(
                organization_id=ctx.ws.organization_id,
                voice_session_id=voice_session_id,
                runtime_mode=runtime_mode,
                ended_at=ended_at,
                ended_reason=ended_reason,
                status=browser_voice_session_status(ended_reason),
                metrics=audio_metrics or None,
            ),
        )
    ctx.ws.voice_transcript_session_started = False
    ctx.ws.voice_transcript_runtime_mode = None
    if ctx.ws.live_voice_buffer is not None:
        await _run_voice_cleanup_step(
            ctx.organization_id,
            "live_buffer",
            ctx.ws.live_voice_buffer.discard(),
        )
        ctx.ws.live_voice_buffer = None
    ctx.ws.voice_call_id = None
    ctx.ws.voice_interaction_sequence = 0
    ctx.ws.voice_interaction_started_at = None
    ctx.ws.voice_interaction_callback = None
    ctx.ws.voice_session_id = None
    ctx.ws.is_voice_mode = False
    ctx.ws.voice_requests.clear()
    ctx.ws.current_voice_request_id = None
    ctx.ws.voice_activity_gate.reset()
    ctx.ws.transport_playback_gate.reset()
    ctx.ws.voice_output_drained_callback = None
    ctx.ws.voice_terminal_callback = None
    ctx.ws.voice_termination_complete = True


async def _play_browser_policy_speech(
    session_state: WSSessionState,
    *,
    text: str,
    source: VoiceRequestSource,
    request_id: UUID | None = None,
    wait_until_played: bool = False,
) -> UUID:
    live_buffer = session_state.live_voice_buffer
    if live_buffer is None:
        raise RuntimeError("Browser voice buffer is unavailable.")
    realtime_speaker = (
        session_state.realtime_manager if session_state.realtime_mode else None
    )
    return await play_policy_speech(
        tts_manager=session_state.tts_manager,
        realtime_speaker=realtime_speaker,
        live_buffer=live_buffer,
        conversation_id=live_buffer.identity.conversation_id,
        text=text,
        source=source,
        session_state=session_state,
        request_id=request_id,
        wait_until_played=wait_until_played,
        wait_for_transport_drain=(
            lambda timeout: session_state.transport_playback_gate.wait_until_drained(
                timeout=timeout
            )
        ),
    )


def _is_browser_speech_active(session_state: WSSessionState) -> bool:
    if session_state.transport_playback_gate.is_active:
        return True
    if (
        session_state.realtime_manager
        and session_state.realtime_manager.is_playback_active()
    ):
        return True
    return bool(
        session_state.tts_manager and session_state.tts_manager.is_playback_active()
    )


async def terminate_browser_voice(
    ctx: SessionContext,
    *,
    reason: str,
    notify_client: bool,
    source: VoiceRequestSource | None = None,
    final_message: str | None = None,
    request_id: UUID | None = None,
) -> bool:
    """Join one cancellation-safe browser voice termination task."""
    started, task = await _ensure_browser_voice_termination(
        ctx,
        reason=reason,
        notify_client=notify_client,
        source=source,
        final_message=final_message,
        request_id=request_id,
    )
    if task is None:
        return False
    await asyncio.shield(task)
    return started


async def request_browser_voice_termination(
    ctx: SessionContext,
    *,
    reason: str,
    notify_client: bool,
    source: VoiceRequestSource | None = None,
    final_message: str | None = None,
    request_id: UUID | None = None,
) -> bool:
    """Start browser voice termination without making its Agent task await itself."""
    started, _ = await _ensure_browser_voice_termination(
        ctx,
        reason=reason,
        notify_client=notify_client,
        source=source,
        final_message=final_message,
        request_id=request_id,
    )
    return started


async def _ensure_browser_voice_termination(
    ctx: SessionContext,
    *,
    reason: str,
    notify_client: bool,
    source: VoiceRequestSource | None,
    final_message: str | None,
    request_id: UUID | None,
) -> tuple[bool, asyncio.Task[bool] | None]:
    """Create the one session-owned termination task and return it."""
    if ctx.ws is None:
        return False, None

    async with ctx.ws.voice_termination_lock:
        if ctx.ws.voice_termination_complete:
            return False, None
        task = ctx.ws.voice_termination_task
        started = task is None or (
            task.done() and not ctx.ws.voice_termination_complete
        )
        if started:
            terminal_reason = ctx.ws.voice_termination_reason or reason
            ctx.ws.voice_termination_reason = terminal_reason
            task = asyncio.create_task(
                _run_browser_voice_termination(
                    ctx,
                    reason=terminal_reason,
                    notify_client=notify_client,
                    source=source,
                    final_message=final_message,
                    request_id=request_id,
                ),
                name="browser-voice-termination",
            )
            task.add_done_callback(_consume_browser_voice_termination_result)
            ctx.ws.voice_termination_task = task

    return started, task


async def _run_browser_voice_termination(
    ctx: SessionContext,
    *,
    reason: str,
    notify_client: bool,
    source: VoiceRequestSource | None,
    final_message: str | None,
    request_id: UUID | None,
) -> bool:
    """Own provider, signaling, projection, and state cleanup exactly once."""
    if ctx.ws is None:
        return False

    if final_message and source is not None:
        if ctx.ws.tts_manager is not None or ctx.ws.realtime_manager is not None:
            try:
                await _play_browser_policy_speech(
                    ctx.ws,
                    text=final_message,
                    source=source,
                    request_id=request_id,
                    wait_until_played=True,
                )
            except Exception as error:
                logger.error(
                    "Terminal browser speech failed reason=%s error_type=%s; "
                    "termination continues.",
                    reason,
                    type(error).__name__,
                )
        else:
            logger.warning(
                "Terminal browser message skipped reason=%s because speech is unavailable.",
                reason,
            )

    from eylo.pipelines.webrtc.singleton import S_webrtc_signaling

    try:
        await S_webrtc_signaling.cleanup_session(
            ctx.organization_id,
            ctx.session_id,
            reason=reason,
            notify_client=notify_client,
        )
    except Exception as error:
        logger.error(
            "Browser signaling termination failed reason=%s error_type=%s.",
            reason,
            type(error).__name__,
        )

    try:
        await cleanup_audio_services(ctx)
    except Exception as error:
        logger.error(
            "Browser audio termination failed reason=%s error_type=%s.",
            reason,
            type(error).__name__,
        )

    ctx.ws.voice_termination_complete = not ctx.ws.is_voice_mode
    return True


def _consume_browser_voice_termination_result(task: asyncio.Task[bool]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Browser voice termination task was cancelled.")
    except Exception as error:
        logger.error(
            "Browser voice termination task failed error_type=%s.",
            type(error).__name__,
        )


async def _terminate_browser_from_transport(
    ctx: SessionContext,
    reason: str,
) -> None:
    await terminate_browser_voice(
        ctx,
        reason=reason,
        notify_client=True,
    )


async def _terminate_browser_from_end_call_phrase(
    ctx: SessionContext,
    request_id: UUID,
    final_message: str | None,
) -> None:
    await terminate_browser_voice(
        ctx,
        reason="user_end_call_phrase",
        notify_client=True,
        source=VoiceRequestSource.END_CALL,
        final_message=final_message,
        request_id=request_id,
    )


async def _initialize_realtime_mode(
    ctx: SessionContext,
    session_state: WSSessionState,
    conversation_id: UUID,
    resolved_realtime: ResolvedRealtime,
    conversation_control: ConversationControl,
) -> None:
    from eylo.pipelines.voice.realtime import (
        RealtimeInteractionCallbacks,
        RealtimeManager,
    )
    from eylo.sockets.realtime.config import RealtimeSessionConfig

    if session_state.voice_call_id is None:
        raise RuntimeError("Realtime voice call identity is not initialized.")
    provider_config = resolved_realtime.config
    config = RealtimeSessionConfig.model_validate(
        {
            "organization_id": session_state.organization_id,
            "conversation_id": conversation_id,
            "agent_id": session_state.agent_id,
            "session_id": session_state.voice_call_id,
            "voice_session_row_id": session_state.voice_session_id,
            "vendor": resolved_realtime.provider.value,
            "model": provider_config["model"],
            "voice": provider_config["voice"],
            "temperature": provider_config.get("temperature"),
            "top_p": provider_config.get("top_p"),
            "max_tokens": provider_config.get("max_tokens"),
            "input_transcription_model": provider_config.get(
                "input_transcription_model"
            ),
            "vad_threshold": provider_config.get("vad_threshold"),
            "vad_silence_ms": provider_config.get("vad_silence_ms"),
            "endpointing_sensitivity": provider_config.get("endpointing_sensitivity"),
            "is_context_compression_enabled": provider_config.get(
                "context_compression_enabled"
            ),
            "context_compression_trigger_tokens": provider_config.get(
                "context_compression_trigger_tokens"
            ),
        }
    )

    session_state.tts_response_queue = asyncio.Queue()
    session_state.tts_interrupt_event = asyncio.Event()
    if session_state.live_voice_buffer is None:
        raise RuntimeError("Realtime voice buffer is not initialized.")

    async def _on_realtime_teardown(reason: str) -> None:
        failed = reason in {
            "realtime_transport_error",
            "realtime_transport_ended",
            "realtime_reconnect_failed",
            "realtime_vendor_error",
            "realtime_handoff_failed",
        }
        payload = {
            "message": (
                "Realtime service failed" if failed else "Realtime session ended"
            ),
            "vendor": resolved_realtime.provider.value,
            "runtime_mode": VoiceRuntimeMode.BROWSER_REALTIME.value,
            "timestamp": arrow.utcnow().timestamp(),
        }
        if failed and session_state.voice_interaction_callback:
            session_state.voice_interaction_callback(VoiceInteractionState.ERROR)
        if failed:
            await _record_voice_provider_fact(
                session_state,
                provider_kind="realtime",
                state="failed",
                vendor=resolved_realtime.provider.value,
            )
        try:
            await S_ws_manager.send_response(
                {
                    "kind": (
                        WsEventAction.STT_ERROR
                        if failed
                        else WsEventAction.STT_DISCONNECTED
                    ),
                    "data": payload,
                },
                session_state.organization_id,
                session_state.session_id,
            )
            await S_ws_manager.send_response(
                {
                    "kind": (
                        WsEventAction.TTS_ERROR
                        if failed
                        else WsEventAction.TTS_DISCONNECTED
                    ),
                    "data": payload,
                },
                session_state.organization_id,
                session_state.session_id,
            )
        except Exception:
            logger.debug("Failed to send realtime disconnect signals")
        await terminate_browser_voice(
            ctx,
            reason=reason,
            notify_client=True,
        )

    def _on_user_activity() -> None:
        _cancel_browser_output(session_state)
        session_state.voice_activity_gate.mark_user_activity()
        session_state.speech_activity_event.set()
        if session_state.voice_interaction_callback:
            session_state.voice_interaction_callback(VoiceInteractionState.LISTENING)

    def _on_processing_started() -> None:
        if session_state.voice_interaction_callback:
            session_state.voice_interaction_callback(VoiceInteractionState.PROCESSING)

    def _on_agent_activity_started() -> None:
        _mark_browser_output_started(session_state)

    def _on_agent_activity_finished() -> None:
        _mark_browser_output_producer_finished(session_state)

    manager = RealtimeManager(
        config=config,
        resolved_realtime=resolved_realtime,
        tts_response_queue=session_state.tts_response_queue,
        tts_interrupt_event=session_state.tts_interrupt_event,
        interaction=RealtimeInteractionCallbacks(
            on_user_activity=_on_user_activity,
            on_processing_started=_on_processing_started,
            on_agent_activity_started=_on_agent_activity_started,
            on_agent_activity_finished=_on_agent_activity_finished,
            on_end_call=partial(
                _terminate_browser_from_end_call_phrase,
                ctx,
            ),
        ),
        end_call_phrases=conversation_control.end_call_phrases,
        end_call_message=conversation_control.end_call_message,
        on_audio_chunk=(
            session_state.audio_recorder.record_agent
            if session_state.audio_recorder
            else None
        ),
        on_teardown=_on_realtime_teardown,
        live_buffer=session_state.live_voice_buffer,
    )
    session_state.realtime_mode = True
    session_state.realtime_manager = manager
    try:
        await manager.initialize()
    except Exception:
        await _record_voice_provider_fact(
            session_state,
            provider_kind="realtime",
            state="failed",
            vendor=resolved_realtime.provider.value,
        )
        raise
    await _record_voice_provider_fact(
        session_state,
        provider_kind="realtime",
        state="connected",
        vendor=resolved_realtime.provider.value,
    )


async def _initialize_stt_service(
    session_state: WSSessionState,
    stt_config: dict[str, Any],
    *,
    stt_api_key: str | None = None,
) -> None:
    session_state.stt_request_queue = asyncio.Queue()
    session_state.stt_response_queue = asyncio.Queue()

    stt_vendor = stt_config["vendor"]
    logger.debug("STT Vendor: %s", stt_vendor)

    session_state.stt_socket = STTRealtime(
        organization_id=session_state.organization_id,
        session_id=session_state.session_id,
        consumer_queue=session_state.stt_response_queue,
        stt_config=stt_config,
        stt_vendor=stt_vendor,
        api_key=stt_api_key,
    )

    stt_task = asyncio.create_task(session_state.stt_socket.initialize())
    session_state.stt_session_tasks["stt_initialize"] = stt_task
    try:
        await _wait_for_provider_ready(
            task=stt_task,
            is_ready=lambda: session_state.stt_socket.is_connected,
            provider_kind="STT",
        )
    except Exception:
        await _record_voice_provider_fact(
            session_state,
            provider_kind="stt",
            state="failed",
            vendor=stt_vendor,
        )
        await _cancel_failed_provider_startup(stt_task)
        session_state.stt_session_tasks.pop("stt_initialize", None)
        session_state.stt_socket = None
        session_state.stt_started = False
        raise

    session_state.stt_started = True
    await _record_voice_provider_fact(
        session_state,
        provider_kind="stt",
        state="connected",
        vendor=stt_vendor,
    )
    _watch_voice_provider_task(
        session_state,
        stt_task,
        provider_kind="stt",
        vendor=stt_vendor,
    )
    logger.info("STT service initialized successfully")


async def _initialize_tts_service(
    session_state: WSSessionState,
    tts_config: dict[str, Any] | None,
    *,
    tts_api_key: str | None = None,
) -> bool:
    if tts_config is None:
        logger.info("TTS is disabled for this session - STT-only mode")
        return False

    logger.info("TTS is enabled for this session - initializing TTS services")

    session_state.tts_request_queue = asyncio.Queue()
    session_state.tts_response_queue = asyncio.Queue()

    logger.info(
        "Initializing TTS producer for queue %s",
        id(session_state.tts_response_queue),
    )

    audio_recorder = getattr(session_state, "audio_recorder", None)
    on_audio_chunk = audio_recorder.record_agent if audio_recorder else None

    def on_playback_started() -> None:
        _mark_browser_output_started(session_state)

    def on_playback_finished() -> None:
        _mark_browser_output_producer_finished(session_state)

    tts_manager = TTSRealtime(
        organization_id=session_state.organization_id,
        session_id=session_state.session_id,
        consumer_queue=session_state.tts_response_queue,
        tts_config=tts_config,
        on_audio_chunk=on_audio_chunk,
        on_playback_started=on_playback_started,
        on_playback_finished=on_playback_finished,
        api_key=tts_api_key,
    )

    session_state.tts_socket = tts_manager
    session_state.tts_manager = tts_manager

    tts_task = asyncio.create_task(session_state.tts_manager.initialize())
    session_state.tts_session_tasks["tts_initialize"] = tts_task
    try:
        await _wait_for_provider_ready(
            task=tts_task,
            is_ready=lambda: session_state.tts_manager.is_connected,
            provider_kind="TTS",
        )
    except Exception:
        await _record_voice_provider_fact(
            session_state,
            provider_kind="tts",
            state="failed",
            vendor=str(tts_config["vendor"]),
        )
        await _cancel_failed_provider_startup(tts_task)
        session_state.tts_session_tasks.pop("tts_initialize", None)
        session_state.tts_socket = None
        session_state.tts_manager = None
        session_state.tts_started = False
        raise

    session_state.tts_started = True
    await _record_voice_provider_fact(
        session_state,
        provider_kind="tts",
        state="connected",
        vendor=str(tts_config["vendor"]),
    )
    _watch_voice_provider_task(
        session_state,
        tts_task,
        provider_kind="tts",
        vendor=str(tts_config["vendor"]),
    )
    logger.info(
        "TTS manager initialized organization_id=%s",
        session_state.organization_id,
    )
    return True


def _watch_voice_provider_task(
    session_state: WSSessionState,
    task: asyncio.Task[None],
    *,
    provider_kind: str,
    vendor: str | None = None,
) -> None:
    """Terminate the call when an already-ready provider fails at runtime."""

    def on_done(completed: asyncio.Task[None]) -> None:
        if completed.cancelled():
            return
        error = completed.exception()
        if error is None or session_state.voice_termination_reason:
            return
        callback = session_state.voice_terminal_callback
        if session_state.voice_interaction_callback:
            session_state.voice_interaction_callback(VoiceInteractionState.ERROR)
        if callback is None:
            logger.error(
                "%s runtime failed without a terminal callback error_type=%s",
                provider_kind.upper(),
                type(error).__name__,
            )
            return
        async def record_and_terminate() -> None:
            await _record_voice_provider_fact(
                session_state,
                provider_kind=provider_kind,
                state="failed",
                vendor=vendor,
            )
            await callback(f"{provider_kind}_runtime_failed")

        termination = asyncio.create_task(
            record_and_terminate(),
            name=f"{provider_kind}-runtime-termination",
        )
        termination.add_done_callback(_consume_provider_termination_result)

    task.add_done_callback(on_done)


def _consume_provider_termination_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Voice provider termination callback was cancelled.")
    except Exception as error:
        logger.error(
            "Voice provider termination callback failed error_type=%s",
            type(error).__name__,
        )


async def _wait_for_provider_ready(
    *,
    task: asyncio.Task[None],
    is_ready: Callable[[], bool],
    provider_kind: str,
) -> None:
    async def wait() -> None:
        while not is_ready():
            if task.done():
                if task.cancelled():
                    raise RuntimeError(
                        f"{provider_kind} provider initialization was cancelled."
                    )
                error = task.exception()
                if error is not None:
                    raise RuntimeError(
                        f"{provider_kind} provider initialization failed."
                    ) from error
                raise RuntimeError(
                    f"{provider_kind} provider initialization ended before readiness."
                )
            await asyncio.sleep(0.01)

    try:
        async with asyncio.timeout(_VOICE_PROVIDER_STARTUP_TIMEOUT_SECONDS):
            await wait()
    except TimeoutError as error:
        raise RuntimeError(f"{provider_kind} provider readiness timed out.") from error


async def _cancel_failed_provider_startup(task: asyncio.Task[None]) -> None:
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def _play_first_message(
    conversation_control: ConversationControl,
    *,
    session_state: WSSessionState,
) -> None:
    first_message = conversation_control.first_message
    mode = conversation_control.first_message_mode

    if not first_message or mode != "assistant-speaks-first":
        return

    try:
        await _play_browser_policy_speech(
            session_state,
            text=first_message,
            source=VoiceRequestSource.GREETING,
        )
    except Exception as error:
        logger.error(
            "First browser message failed error_type=%s; call continues.",
            type(error).__name__,
        )
        return
    logger.info("First browser message queued chars=%d", len(first_message))


async def _enforce_max_duration(
    ctx: SessionContext,
    max_seconds: int,
    end_call_message: str | None,
) -> None:
    try:
        await asyncio.sleep(max_seconds)
        logger.info(
            "Max duration (%ds) reached organization_id=%s",
            max_seconds,
            ctx.organization_id,
        )
        await terminate_browser_voice(
            ctx,
            reason="max_duration",
            notify_client=True,
            source=VoiceRequestSource.MAX_DURATION,
            final_message=end_call_message,
        )
    except asyncio.CancelledError:
        pass


async def _monitor_silence(
    ctx: SessionContext,
    silence_config: SilenceConfig,
    end_call_message: str | None,
) -> None:
    if ctx.ws is None:
        return
    session_state = ctx.ws

    async def play_reminder(message: str) -> None:
        if session_state.tts_manager is None and session_state.realtime_manager is None:
            session_state.voice_activity_gate.mark_agent_activity_finished()
            return
        try:
            await _play_browser_policy_speech(
                session_state,
                text=message,
                source=VoiceRequestSource.SILENCE,
            )
        except Exception as error:
            logger.error(
                "Silence reminder failed error_type=%s; monitor continues.",
                type(error).__name__,
            )
            session_state.voice_activity_gate.mark_agent_activity_finished()

    async def end_for_silence(elapsed: float) -> None:
        logger.info(
            "Ending call after %ds silence organization_id=%s",
            int(elapsed),
            ctx.organization_id,
        )
        await terminate_browser_voice(
            ctx,
            reason="silence_timeout",
            notify_client=True,
            source=VoiceRequestSource.SILENCE,
            final_message=end_call_message,
        )

    try:
        await run_silence_monitor(
            config=silence_config,
            speech_activity_event=session_state.speech_activity_event,
            activity=session_state.voice_activity_gate,
            is_agent_thinking=lambda: session_state.is_agent_thinking,
            is_tts_active=lambda: _is_browser_speech_active(session_state),
            on_reminder=play_reminder,
            on_timeout=end_for_silence,
        )
    except asyncio.CancelledError:
        pass


async def _start_browser_interaction_policies(
    ctx: SessionContext,
    voice_config: VoiceConfig,
) -> None:
    """Start provider-neutral disclosure, greeting, and timing policies."""
    session_state = ctx.ws

    if consent.is_pending(session_state):

        async def deliver_disclosure(message: str) -> bool:
            await _play_browser_policy_speech(
                session_state,
                text=message,
                source=VoiceRequestSource.CONSENT,
            )
            return True

        await consent.announce_and_grant(
            session_state,
            None,
            _compliance_plan(voice_config).recording_consent_message,
            deliver=deliver_disclosure,
        )

    conversation_control = voice_config.conversation_control
    if conversation_control.first_message:
        await _play_first_message(
            conversation_control,
            session_state=session_state,
        )

    if not _is_browser_speech_active(session_state):
        _mark_browser_awaiting_user(session_state)

    if conversation_control.max_duration_seconds > 0:
        session_state.voice_policy_tasks["max_duration_timeout"] = asyncio.create_task(
            _enforce_max_duration(
                ctx,
                conversation_control.max_duration_seconds,
                conversation_control.end_call_message,
            )
        )

    silence_config = voice_config.silence
    if silence_config and should_start_silence_monitor(silence_config):
        session_state.voice_policy_tasks["silence_monitor"] = asyncio.create_task(
            _monitor_silence(
                ctx,
                silence_config,
                conversation_control.end_call_message,
            )
        )


async def handle_audio_config(
    event: WsRequestEvent,
    ctx: SessionContext,
) -> WsResponse | None:
    """Initialize browser voice pipeline services from an audio config event."""
    try:
        if ctx.ws.stt_started or ctx.ws.realtime_mode:
            logger.warning(
                "audio:config already initialized organization_id=%s; "
                "ignoring duplicate request",
                ctx.organization_id,
            )
            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.AUDIO_CONFIG,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
                data={"initialized": True, "reused": True},
            )

        if not event.data:
            logger.error("audio:config event received with no data")
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Audio configuration is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        conversation_id = event.data.get("conversation_id", None)
        if not conversation_id:
            logger.error("No conversation_id found in audio_config event")
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            conversation_uuid = UUID(str(conversation_id))
        except ValueError:
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation is not valid",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not ctx.allows_conversation(conversation_uuid):
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await S_ws_manager.associate_conversation_session(
            conversation_id=conversation_uuid,
            session_id=ctx.session_id,
            organization_id=ctx.organization_id,
        )

        async with start_transaction(ro=True):
            participants = await ConversationParticipantService().list_by_conversation(
                conversation_id=conversation_id
            )

        if not participants:
            logger.error("No participants found for the conversation")
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        agents = ConversationParticipantService().filter_primary_agent_participant(
            participants
        )
        if not agents:
            agents = ConversationParticipantService().filter_agent_participants(
                participants
            )
        if not agents:
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation has no usable agent",
                status_code=status.HTTP_409_CONFLICT,
            )
        agent_participant = agents[0]
        agent_id = agent_participant.agent_id
        agent_revision = agent_participant.agent_revision
        if agent_id is None or agent_revision is None:
            logger.error("Conversation has no exact published agent revision")
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation agent is not published",
                status_code=status.HTTP_409_CONFLICT,
            )
        async with start_transaction(ro=True) as agent_db:
            from eylo.modules.templates.domain import TemplateConsumerKind
            from eylo.pipelines.agents import build_executable_agent_resolver

            executable = await build_executable_agent_resolver(agent_db).resolve_exact(
                organization_id=ctx.organization_id,
                agent_id=agent_id,
                revision=agent_revision,
                consumer_kind=TemplateConsumerKind.REALTIME_VOICE,
            )
            agent = executable.agent
            await AgentLLMReadinessService().ensure_ready(agent)
        ctx.ws.agent_id = agent_id
        ctx.ws.agent_revision = agent_revision
        ctx.ws.webrtc_provider_config_id = agent.webrtc_provider_config_id
        ctx.ws.webrtc_provider_config_revision = agent.webrtc_provider_config_revision

        contacts = ConversationParticipantService().filter_primary_contact_participant(
            participants
        )
        if not contacts:
            contacts = ConversationParticipantService().filter_contact_participants(
                participants
            )
        try:
            contact_id = UUID(contacts[0].entity_id) if contacts else None
        except ValueError:
            contact_id = None
        if not contact_id:
            logger.error("No contacts found for the conversation")
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Conversation not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        ctx.ws.contact_id = contact_id

        ctx.ws.stt_encoding_info = STTEncodingInfo.model_validate(
            {
                "sample_rate": event.data.get("sample_rate", _DEFAULT_SAMPLE_RATE),
                "channels": event.data.get("channels", 1),
                "encoding": event.data.get("encoding", "LINEAR16"),
                "language": event.data.get("language", "en-US"),
            }
        )

        voice_config = VoiceConfig.model_validate(executable.voice_config or {})

        resolved_stt: ResolvedSTT | None = None
        resolved_tts: ResolvedTTS | None = None
        resolved_realtime: ResolvedRealtime | None = None
        decomposed_identity: DecomposedVoiceRuntimeIdentity | None = None
        stt_config: dict[str, Any] | None = None
        tts_config: dict[str, Any] | None = None
        if voice_config.realtime_provider_config_id is None:
            async with start_transaction(ro=True) as voice_runtime_db:
                resolved_stt, resolved_tts = await resolve_decomposed_voice_runtime(
                    ctx.organization_id,
                    voice_config,
                    db=voice_runtime_db,
                )
            stt_transport: dict[str, object] = {}
            tts_transport: dict[str, object] = {}
            if resolved_stt.provider is STTProviders.AMAZON_TRANSCRIBE:
                # Browser media is normalized to signed 16-bit mono PCM at
                # 16 kHz before it reaches STT. This is a transport fact, not
                # an operator-configurable provider default.
                stt_transport.update(sample_rate=16000, encoding="pcm_s16le")
            if resolved_tts.provider is TTSProviders.AMAZON_POLLY:
                # The browser output track and recorder consume 16 kHz PCM.
                tts_transport.update(sample_rate=16000, encoding="pcm_s16le")
            stt_config = build_stt_runtime_config(
                voice_config,
                resolved_stt,
                transport=stt_transport,
            )
            tts_config = build_tts_runtime_config(
                resolved_tts,
                transport=tts_transport,
            )
            decomposed_identity = DecomposedVoiceRuntimeIdentity.from_resolved(
                resolved_stt,
                resolved_tts,
            )
        else:
            async with start_transaction(ro=True) as voice_runtime_db:
                resolved_realtime = await resolve_realtime_voice_runtime(
                    ctx.organization_id,
                    voice_config,
                    db=voice_runtime_db,
                )

        # Set before anything below can log. Outside the `if voice_config`
        # block on purpose: an unconfigured agent must still get the schema
        # default rather than whatever the previous session left behind.
        redact_logs.set(
            voice_config.compliance.redact_pii_in_logs
            if voice_config
            else CompliancePlan().redact_pii_in_logs
        )

        if resolved_realtime is not None:
            from eylo.sockets.realtime.factory import RealtimeFactory

            RealtimeFactory.validate(
                resolved_realtime.provider.value,
                resolved_realtime,
            )

        if voice_config:
            # Resolve observability once, here, where the config is already
            # loaded; teardown then needs no lookup.
            observability = voice_config.observability
            ctx.ws.metrics_enabled = observability.metrics_enabled
            ctx.ws.vendor_latency_tracking_enabled = (
                observability.vendor_latency_tracking_enabled
            )

            apply_voice_interaction_config(ctx.ws, voice_config)

        voice_call_id = str(uuid4())
        _maybe_initialize_recorder(
            ctx.ws,
            conversation_uuid,
            voice_config,
            tts_config,
            recording_session_id=voice_call_id,
        )
        ctx.voice_session_id = await _start_browser_voice_session(
            ctx.ws,
            conversation_uuid,
            voice_config,
            contact_id=contact_id,
            contact_participant_id=contacts[0].id,
            agent_participant_id=agent_participant.id,
            voice_call_id=voice_call_id,
            resolved_realtime=resolved_realtime,
            decomposed_identity=decomposed_identity,
        )

        ctx.ws.voice_terminal_callback = partial(
            _terminate_browser_from_transport,
            ctx,
        )

        if resolved_realtime is not None:
            await _initialize_realtime_mode(
                ctx,
                ctx.ws,
                conversation_uuid,
                resolved_realtime,
                voice_config.conversation_control,
            )
            logger.info(
                "Realtime mode initialized for conversation %s (vendor=%s)",
                conversation_id,
                resolved_realtime.provider.value,
            )
            await _send_realtime_ready_signals(
                ctx,
                resolved_realtime.provider.value,
            )
        else:
            if not stt_config or resolved_stt is None or resolved_tts is None:
                raise RuntimeError(
                    "Published decomposed voice authority is incomplete."
                )

            await _initialize_stt_service(
                ctx.ws,
                stt_config,
                stt_api_key=resolved_stt.secret,
            )

            await _initialize_tts_service(
                ctx.ws,
                tts_config,
                tts_api_key=resolved_tts.secret,
            )

            live_buffer = ctx.ws.live_voice_buffer
            if live_buffer is None:
                raise RuntimeError("Decomposed voice buffer is not initialized.")
            live_turn_runner = LiveVoiceTurnRunner(
                live_buffer,
                session_state=ctx.ws,
            )
            ctx.ws.live_voice_turn_runner = live_turn_runner
            if ctx.ws.tts_manager is not None:
                ctx.ws.tts_manager.set_turn_outcome_callback(
                    live_turn_runner.record_speech_outcome
                )

            user_transcript_task = asyncio.create_task(
                write_user_transcript(
                    ctx.ws.stt_response_queue,
                    conversation_uuid,
                    ctx.ws.tts_manager,
                    ctx.ws.tts_interrupt_event,
                    ctx.ws.speech_activity_event,
                    on_interrupt=live_turn_runner.interrupt,
                    on_end_call=partial(
                        _terminate_browser_from_end_call_phrase,
                        ctx,
                    ),
                    on_final_transcript=live_turn_runner.submit,
                    voice_config=voice_config,
                    session_state=ctx.ws,
                    voice_session_id=ctx.ws.voice_call_id,
                    voice_session_row_id=ctx.ws.voice_session_id,
                    voice_runtime_mode=VoiceRuntimeMode.BROWSER_DECOMPOSED,
                    live_buffer=live_buffer,
                )
            )
            ctx.ws.stt_session_tasks["user_transcript_writer"] = user_transcript_task

        # Recording delivery remains secondary: failure stays pending and never
        # prevents the call. Greeting/timing behavior is shared by both runtime
        # modes and therefore starts only after their speech path is ready.
        await _start_browser_interaction_policies(ctx, voice_config)

        logger.info(
            "Audio config initialized successfully for conversation %s",
            conversation_id,
        )
        return WsResponse(
            status=status.HTTP_200_OK,
            kind=WsEventAction.AUDIO_CONFIG,
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            request_id=event.request_id,
            data={
                "initialized": True,
                "runtime_mode": (
                    VoiceRuntimeMode.BROWSER_REALTIME.value
                    if resolved_realtime is not None
                    else VoiceRuntimeMode.BROWSER_DECOMPOSED.value
                ),
            },
        )

    except NotConfiguredError as error:
        if ctx.ws and ctx.ws.is_voice_mode:
            try:
                await terminate_browser_voice(
                    ctx,
                    reason="voice_configuration_failed",
                    notify_client=False,
                )
            except Exception as cleanup_error:
                logger.error(
                    "Audio configuration rollback failed error_type=%s",
                    type(cleanup_error).__name__,
                )
        return not_configured_response(
            error,
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            request_id=event.request_id,
        )
    except Exception as error:
        logger.error(
            "Audio configuration failed error_type=%s",
            type(error).__name__,
        )
        if ctx.ws and ctx.ws.voice_interaction_callback:
            ctx.ws.voice_interaction_callback(VoiceInteractionState.ERROR)
        if ctx.ws and (
            ctx.ws.is_voice_mode
            or ctx.ws.audio_recorder is not None
            or ctx.ws.realtime_manager is not None
            or ctx.ws.stt_started
            or ctx.ws.tts_started
        ):
            try:
                await terminate_browser_voice(
                    ctx,
                    reason="voice_initialization_failed",
                    notify_client=False,
                )
            except Exception as cleanup_error:
                logger.error(
                    "Audio configuration rollback failed error_type=%s",
                    type(cleanup_error).__name__,
                )
        return build_ws_error_response(
            event,
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            message="Voice initialization failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
