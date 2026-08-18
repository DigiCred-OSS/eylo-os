"""Telephony voice pipeline setup helpers.

The telephony socket route owns provider WebSocket receive/send mechanics. This
module owns the platform voice pipeline attached to a call: STT/TTS manager
creation, recorder wiring, transcript session lifecycle, and transcript writing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import arrow

from eylo.common.database import start_transaction
from eylo.modules.agents.domain import ResolvedExecutableAgent
from eylo.modules.telephony.lifecycle import link_call_voice_session
from eylo.modules.voice.schemas.api import SilenceConfig, VoiceConfig
from eylo.modules.voice_configs.catalog import TTSProviders
from eylo.modules.voice_configs.domain import ResolvedSTT, ResolvedTTS
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.modules.voice_transcripts.schemas.indb import VoiceSessionCreate
from eylo.modules.voice_transcripts.services.indb import VoiceTranscriptService
from eylo.pipelines.telephony.sessions import CallSession
from eylo.pipelines.voice.audio_transport import StreamingAudioTranscoder
from eylo.pipelines.voice.interaction_config import apply_voice_interaction_config
from eylo.pipelines.voice.lifecycle_policy import (
    monitor_silence,
    should_start_silence_monitor,
)
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceBufferIdentity,
)
from eylo.pipelines.voice.live_runner import LiveVoiceTurnRunner
from eylo.pipelines.voice.policy_speech import play_policy_speech
from eylo.pipelines.voice.provider_runtime import (
    DecomposedVoiceRuntimeIdentity,
    build_stt_runtime_config,
    build_tts_runtime_config,
    resolve_decomposed_voice_runtime,
)
from eylo.pipelines.voice.request_state import VoiceRequestSource
from eylo.pipelines.voice.stt import STTRealtime
from eylo.pipelines.voice.transcripts import write_user_transcript
from eylo.pipelines.voice.tts import TTSRealtime
from eylo.pipelines.websocket.singleton import S_ws_manager
from eylo.sockets.telephony.base import (
    CallEndedReason,
    TelephonyControlAccepted,
)
from eylo.sockets.telephony.manager import TelephonyRealtime
from eylo.sockets.tts.schemas import TTSAudioFormat

logger = logging.getLogger(__name__)


@dataclass
class VoicePipelineBundle:
    """Return contract for telephony voice pipeline initialization."""

    stt: STTRealtime
    tts: TTSRealtime
    tts_audio_transcoder: StreamingAudioTranscoder
    stt_request_queue: asyncio.Queue
    stt_response_queue: asyncio.Queue
    tts_request_queue: asyncio.Queue
    tts_response_queue: asyncio.Queue
    stt_tasks: dict[str, asyncio.Task]
    tts_tasks: dict[str, asyncio.Task]
    voice_config: VoiceConfig | None
    stt_config: dict[str, Any]
    stt_vendor: str
    tts_config: dict[str, Any]
    runtime_identity: DecomposedVoiceRuntimeIdentity


def apply_voice_bundle_to_session(
    sess: CallSession, voice_bundle: VoicePipelineBundle
) -> None:
    if voice_bundle.stt_request_queue:
        sess.stt_request_queue = voice_bundle.stt_request_queue
    if voice_bundle.stt_response_queue:
        sess.stt_response_queue = voice_bundle.stt_response_queue
    if voice_bundle.tts_request_queue:
        sess.tts_request_queue = voice_bundle.tts_request_queue
    if voice_bundle.tts_response_queue:
        sess.tts_response_queue = voice_bundle.tts_response_queue
    if voice_bundle.stt:
        sess.stt = voice_bundle.stt
    if voice_bundle.tts:
        sess.tts = voice_bundle.tts
    sess.tts_audio_transcoder = voice_bundle.tts_audio_transcoder
    if voice_bundle.stt_tasks:
        sess.stt_tasks = voice_bundle.stt_tasks
    if voice_bundle.tts_tasks:
        sess.tts_tasks = voice_bundle.tts_tasks
    if voice_bundle.voice_config:
        sess.voice_config = voice_bundle.voice_config


def collect_call_audio_metrics(sess: CallSession) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if sess.stt:
        metrics["stt"] = sess.stt.metrics
    if sess.tts:
        metrics["tts"] = sess.tts.metrics_snapshot().model_dump()
    metrics["transport"] = {
        "carrier_audio_chunks": sess.carrier_audio_chunks,
        "carrier_audio_bytes": sess.carrier_audio_bytes,
        "comfort_audio_chunks": sess.comfort_audio_chunks,
        "comfort_audio_bytes": sess.comfort_audio_bytes,
    }
    return metrics


async def terminate_telephony_voice(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
    ended_reason: CallEndedReason,
    source: VoiceRequestSource,
    final_message: str | None = None,
    request_id: UUID | None = None,
) -> bool:
    """Speak an optional final message, then end the active carrier call once."""
    async with sess.termination_lock:
        if sess.termination_requested:
            return False
        sess.termination_requested = True
        sess.ended_reason = ended_reason

        session_state = (
            S_ws_manager.get_session_state(
                sess.organization_id,
                sess.auth_session_token,
            )
            if sess.organization_id and sess.auth_session_token
            else None
        )
        if (
            final_message
            and sess.tts is not None
            and sess.live_voice_buffer is not None
            and sess.conversation_id is not None
        ):
            try:
                await play_policy_speech(
                    tts_manager=sess.tts,
                    live_buffer=sess.live_voice_buffer,
                    conversation_id=sess.conversation_id,
                    text=final_message,
                    source=source,
                    session_state=session_state,
                    request_id=request_id,
                    wait_until_played=True,
                )
            except Exception as error:
                logger.error(
                    "Terminal telephony speech failed call=%s error_type=%s; "
                    "termination continues.",
                    sess.call_sid,
                    type(error).__name__,
                )

        try:
            result = await telephony_manager.end_call(sess.call_sid)
        except Exception as error:
            logger.error(
                "Carrier termination failed call=%s error_type=%s.",
                sess.call_sid,
                type(error).__name__,
            )
        else:
            if isinstance(result, TelephonyControlAccepted):
                return True
            sess.extra_data["termination_failure_code"] = result.failure_code
            logger.error(
                "Carrier termination was not accepted call=%s failure_code=%s.",
                sess.call_sid,
                result.failure_code,
            )

        sess.ended_reason = CallEndedReason.ERROR_PROVIDER_DISCONNECTED
        try:
            await telephony_manager.close_media_stream()
        except Exception as error:
            logger.error(
                "Carrier media close failed call=%s error_type=%s.",
                sess.call_sid,
                type(error).__name__,
            )
        return False


def bind_telephony_voice_activity(sess: CallSession) -> None:
    """Connect shared TTS activity to the registered telephony WS session."""
    if sess.tts is None or not sess.organization_id or not sess.auth_session_token:
        return
    session_state = S_ws_manager.get_session_state(
        sess.organization_id,
        sess.auth_session_token,
    )
    if session_state is None:
        raise RuntimeError("Registered telephony WS session is unavailable.")
    if sess.voice_config is not None:
        apply_voice_interaction_config(session_state, sess.voice_config)
    sess.tts.set_playback_callbacks(
        started=session_state.voice_activity_gate.mark_agent_activity_started,
        finished=session_state.voice_activity_gate.mark_agent_activity_finished,
    )


def start_telephony_voice_policy_tasks(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
) -> None:
    """Start provider-independent duration and silence policy for one call."""
    if (
        sess.voice_config is None
        or not sess.organization_id
        or not sess.auth_session_token
    ):
        return
    session_state = S_ws_manager.get_session_state(
        sess.organization_id,
        sess.auth_session_token,
    )
    if session_state is None:
        raise RuntimeError("Registered telephony WS session is unavailable.")

    if not bool(sess.tts and sess.tts.is_playback_active()):
        session_state.voice_activity_gate.mark_agent_activity_finished()

    conversation_control = sess.voice_config.conversation_control
    if conversation_control.max_duration_seconds > 0:
        sess.policy_tasks["max_duration_timeout"] = asyncio.create_task(
            _enforce_telephony_max_duration(
                sess=sess,
                telephony_manager=telephony_manager,
                max_seconds=conversation_control.max_duration_seconds,
                final_message=conversation_control.end_call_message,
            )
        )

    silence_config = sess.voice_config.silence
    if should_start_silence_monitor(silence_config):
        sess.policy_tasks["silence_monitor"] = asyncio.create_task(
            _monitor_telephony_silence(
                sess=sess,
                telephony_manager=telephony_manager,
                silence_config=silence_config,
                final_message=conversation_control.end_call_message,
            )
        )


async def start_telephony_agent_greeting(sess: CallSession) -> bool:
    """Queue the configured Agent greeting when no call-specific opener exists."""
    if (
        sess.voice_config is None
        or sess.tts is None
        or sess.live_voice_buffer is None
        or sess.conversation_id is None
    ):
        return False
    conversation_control = sess.voice_config.conversation_control
    if (
        conversation_control.first_message_mode != "assistant-speaks-first"
        or not conversation_control.first_message
    ):
        return False
    session_state = (
        S_ws_manager.get_session_state(
            sess.organization_id,
            sess.auth_session_token,
        )
        if sess.organization_id and sess.auth_session_token
        else None
    )
    await play_policy_speech(
        tts_manager=sess.tts,
        live_buffer=sess.live_voice_buffer,
        conversation_id=sess.conversation_id,
        text=conversation_control.first_message,
        source=VoiceRequestSource.GREETING,
        session_state=session_state,
    )
    logger.info(
        "Agent greeting queued for telephony call %s chars=%d.",
        sess.call_sid,
        len(conversation_control.first_message),
    )
    return True


async def _enforce_telephony_max_duration(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
    max_seconds: int,
    final_message: str | None,
) -> None:
    try:
        await asyncio.sleep(max_seconds)
        logger.info(
            "Max duration (%ds) reached for telephony call %s.",
            max_seconds,
            sess.call_sid,
        )
        await terminate_telephony_voice(
            sess=sess,
            telephony_manager=telephony_manager,
            ended_reason=CallEndedReason.EXCEEDED_MAX_DURATION,
            source=VoiceRequestSource.MAX_DURATION,
            final_message=final_message,
        )
    except asyncio.CancelledError:
        raise


async def _monitor_telephony_silence(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
    silence_config: SilenceConfig,
    final_message: str | None,
) -> None:
    if (
        sess.tts is None
        or sess.live_voice_buffer is None
        or sess.conversation_id is None
        or not sess.organization_id
        or not sess.auth_session_token
    ):
        return
    session_state = S_ws_manager.get_session_state(
        sess.organization_id,
        sess.auth_session_token,
    )
    if session_state is None:
        raise RuntimeError("Registered telephony WS session is unavailable.")

    async def play_reminder(message: str) -> None:
        try:
            await play_policy_speech(
                tts_manager=sess.tts,
                live_buffer=sess.live_voice_buffer,
                conversation_id=sess.conversation_id,
                text=message,
                source=VoiceRequestSource.SILENCE,
                session_state=session_state,
            )
        except Exception as error:
            logger.error(
                "Telephony silence reminder failed call=%s error_type=%s; "
                "monitor continues.",
                sess.call_sid,
                type(error).__name__,
            )
            session_state.voice_activity_gate.mark_agent_activity_finished()

    async def end_for_silence(elapsed: float) -> None:
        logger.info(
            "Ending telephony call %s after %ds silence.",
            sess.call_sid,
            int(elapsed),
        )
        await terminate_telephony_voice(
            sess=sess,
            telephony_manager=telephony_manager,
            ended_reason=CallEndedReason.SILENCE_TIMED_OUT,
            source=VoiceRequestSource.SILENCE,
            final_message=final_message,
        )

    try:
        await monitor_silence(
            config=silence_config,
            speech_activity_event=session_state.speech_activity_event,
            activity=session_state.voice_activity_gate,
            is_agent_thinking=lambda: session_state.is_agent_thinking,
            is_tts_active=sess.tts.is_playback_active,
            on_reminder=play_reminder,
            on_timeout=end_for_silence,
        )
    except asyncio.CancelledError:
        raise


def maybe_initialize_telephony_recorder(
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
) -> None:
    from eylo.common.config import settings

    if not settings.ENABLE_VOICE_RECORDING:
        return
    if not sess.organization_id or not sess.conversation_id:
        return

    from eylo.pipelines.voice.browser import _artifact_plan, _compliance_plan

    if not _artifact_plan(sess.voice_config).audio_storage_enabled:
        # This path used to check only the deployment kill switch, so an agent
        # with audio storage turned off was still recorded over the phone.
        return

    def build() -> None:
        _build_telephony_recorder(sess, telephony_manager)

    try:
        build()
    except Exception as error:
        logger.error(
            "Voice recorder initialization failed for telephony session %s "
            "error_type=%s; call continues.",
            sess.call_sid,
            type(error).__name__,
        )
        return
    if _compliance_plan(sess.voice_config).recording_consent_required:
        # Notification is attempted before the greeting, but recording is the
        # primary flow and begins independently.
        sess.recording_consent_state = "pending"
        return

    sess.recording_consent_state = "not_required"


def _build_telephony_recorder(
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
) -> None:
    from eylo.pipelines.voice.recording import AudioRecorder

    input_format = telephony_manager.get_config() or {}
    output_format = telephony_manager.get_output_format() or {}

    user_sample_rate = int(input_format.get("sample_rate", 8000))
    user_encoding = str(input_format.get("encoding", "pcm_s16le"))
    agent_sample_rate = int(output_format.get("sample_rate", 8000))
    agent_encoding = str(output_format.get("encoding", "pcm_s16le"))

    sess.audio_recorder = AudioRecorder(
        organization_id=sess.organization_id,
        conversation_id=sess.conversation_id,
        session_id=sess.call_sid,
        storage_provider_config_id=(
            sess.voice_config.storage_provider_config_id if sess.voice_config else None
        ),
        storage_provider_config_revision=(
            sess.voice_config.storage_provider_config_revision
            if sess.voice_config
            else None
        ),
        user_sample_rate=user_sample_rate,
        agent_sample_rate=agent_sample_rate,
        user_encoding=user_encoding,
        agent_encoding=agent_encoding,
    )

    logger.info(
        "Voice recorder initialized for telephony session %s",
        sess.call_sid,
    )


async def start_telephony_voice_session(
    sess: CallSession,
    provider: str,
    runtime_identity: DecomposedVoiceRuntimeIdentity,
) -> None:
    if not sess.organization_id or not sess.conversation_id or not sess.user_session_id:
        raise RuntimeError("Telephony user-session authority is incomplete.")
    if sess.voice_config is None:
        raise RuntimeError("Telephony voice config is not initialized.")
    canonical_storage_requested = sess.voice_config.artifacts.transcript_storage_enabled
    compliance = sess.voice_config.compliance

    async with start_transaction():
        voice_service = VoiceTranscriptService()
        voice_session = await voice_service.start_session(
            VoiceSessionCreate(
                organization_id=sess.organization_id,
                conversation_id=sess.conversation_id,
                user_session_id=sess.user_session_id,
                session_id=sess.call_sid,
                runtime_mode=VoiceRuntimeMode.TELEPHONY,
                transport=provider,
                agent_id=sess.agent_id,
                agent_revision=sess.agent_revision,
                started_at=sess.started_at or arrow.utcnow().datetime,
                stt_vendor=runtime_identity.stt_vendor,
                stt_model=runtime_identity.stt_model,
                tts_vendor=runtime_identity.tts_vendor,
                tts_model=runtime_identity.tts_model,
                tts_voice=runtime_identity.tts_voice,
                provider_call_id=sess.call_sid,
                telephony_provider=provider,
                from_number=sess.from_number,
                to_number=sess.to_number,
                recording_enabled=sess.audio_recorder is not None,
                audio_format="wav",
                telephony_call_id=sess.call_id,
                meta={
                    "canonical_storage_requested": canonical_storage_requested,
                    "store_raw_vendor_payloads": compliance.store_raw_vendor_payloads,
                    "allow_sensitive_metadata": compliance.allow_sensitive_metadata,
                    "redact_pii_in_transcripts": compliance.redact_pii_in_transcripts,
                    "recording_consent_required": (
                        compliance.recording_consent_required
                    ),
                },
            )
        )
        if sess.call_id is not None:
            await link_call_voice_session(
                call_id=sess.call_id,
                organization_id=sess.organization_id,
                voice_session_id=voice_session.id,
                db=voice_service.repository.db_session,
            )
    sess.voice_session_id = voice_session.id
    if sess.audio_recorder is not None:
        sess.audio_recorder.bind_voice_session(
            voice_session_id=voice_session.id,
            telephony_call_id=sess.call_id,
        )
    sess.live_voice_buffer = LiveVoiceBuffer(
        LiveVoiceBufferIdentity(
            organization_id=sess.organization_id,
            conversation_id=sess.conversation_id,
            session_id=sess.call_sid,
            voice_session_id=voice_session.id,
            runtime_mode=VoiceRuntimeMode.TELEPHONY,
            canonical_storage_requested=canonical_storage_requested,
        )
    )


async def teardown_voice_pipeline_bundle(
    voice_bundle: VoicePipelineBundle | None,
) -> None:
    if not voice_bundle:
        return

    from eylo.runtime.tasks import teardown_long_running_tasks, teardown_queues

    await teardown_long_running_tasks(
        {**voice_bundle.stt_tasks, **voice_bundle.tts_tasks}
    )
    await teardown_queues(
        [
            voice_bundle.stt_response_queue,
            voice_bundle.stt_request_queue,
            voice_bundle.tts_response_queue,
            voice_bundle.tts_request_queue,
        ],
        join_timeout=1,
    )
    await voice_bundle.stt.disconnect()
    await voice_bundle.tts.disconnect()


def build_stt_config(
    *,
    telephony_manager: TelephonyRealtime,
    voice_config: VoiceConfig | None,
    resolved_stt: ResolvedSTT,
) -> tuple[dict[str, Any], str]:
    if voice_config is None:
        raise RuntimeError("Published Voice Config is required for telephony STT.")
    stt_config = build_stt_runtime_config(
        voice_config,
        resolved_stt,
        transport=telephony_manager.get_config(),
    )
    return stt_config, resolved_stt.provider.value


def build_tts_config(
    *,
    telephony_manager: TelephonyRealtime,
    voice_config: VoiceConfig | None,
    resolved_tts: ResolvedTTS,
) -> dict[str, Any]:
    del voice_config
    transport_config: dict[str, object] = {}
    if resolved_tts.provider is TTSProviders.AMAZON_POLLY:
        # Polly can emit carrier-rate PCM directly. The carrier codec remains
        # a separate target and is applied by StreamingAudioTranscoder.
        carrier_format = TTSAudioFormat.from_mapping(
            telephony_manager.get_output_format()
        )
        transport_config.update(
            sample_rate=carrier_format.sample_rate,
            encoding="pcm_s16le",
        )
    return build_tts_runtime_config(
        resolved_tts,
        transport=transport_config,
    )


async def init_voice_pipeline(
    *,
    organization_id: UUID,
    executable_agent: ResolvedExecutableAgent,
    call_sid: str,
    telephony_manager: TelephonyRealtime,
) -> VoicePipelineBundle:
    async with start_transaction() as voice_config_session:
        if executable_agent.agent.organization_id != organization_id:
            raise ValueError("Executable voice agent belongs to another organization.")
        voice_config = VoiceConfig.model_validate(executable_agent.voice_config or {})
        resolved_stt, resolved_tts = await resolve_decomposed_voice_runtime(
            organization_id,
            voice_config,
            db=voice_config_session,
        )

    stt_config, stt_vendor = build_stt_config(
        telephony_manager=telephony_manager,
        voice_config=voice_config,
        resolved_stt=resolved_stt,
    )

    tts_config = build_tts_config(
        telephony_manager=telephony_manager,
        voice_config=voice_config,
        resolved_tts=resolved_tts,
    )

    stt_request_queue = asyncio.Queue()
    stt_response_queue = asyncio.Queue()
    tts_request_queue = asyncio.Queue()
    tts_response_queue = asyncio.Queue()

    stt = STTRealtime(
        organization_id=organization_id,
        session_id=call_sid,
        consumer_queue=stt_response_queue,
        stt_config=stt_config,
        stt_vendor=stt_vendor,
        api_key=resolved_stt.secret,
    )
    stt_tasks = {"stt_initialize": asyncio.create_task(stt.initialize())}

    tts = TTSRealtime(
        organization_id=organization_id,
        session_id=call_sid,
        consumer_queue=tts_response_queue,
        tts_config=tts_config,
        api_key=resolved_tts.secret,
    )
    tts_audio_transcoder = StreamingAudioTranscoder(
        source=tts.output_audio_format,
        target=TTSAudioFormat.from_mapping(telephony_manager.get_output_format()),
    )
    tts_tasks = {"tts_initialize": asyncio.create_task(tts.initialize())}

    return VoicePipelineBundle(
        voice_config=voice_config,
        stt_config=stt_config,
        stt_vendor=stt_vendor,
        tts_config=tts_config,
        stt_request_queue=stt_request_queue,
        stt_response_queue=stt_response_queue,
        tts_request_queue=tts_request_queue,
        tts_response_queue=tts_response_queue,
        stt=stt,
        tts=tts,
        tts_audio_transcoder=tts_audio_transcoder,
        stt_tasks=stt_tasks,
        tts_tasks=tts_tasks,
        runtime_identity=DecomposedVoiceRuntimeIdentity.from_resolved(
            resolved_stt,
            resolved_tts,
        ),
    )


async def wait_for_voice_pipeline_ready(
    bundle: VoicePipelineBundle,
    *,
    timeout_seconds: float = 15.0,
) -> None:
    """Wait until STT and TTS are live or expose their initializer failure."""

    async def wait_until_ready() -> None:
        while not (bundle.stt.is_connected and bundle.tts.is_connected):
            for task in (
                bundle.stt_tasks["stt_initialize"],
                bundle.tts_tasks["tts_initialize"],
            ):
                if task.done():
                    if task.cancelled():
                        raise RuntimeError(
                            "Voice provider initialization was cancelled."
                        )
                    error = task.exception()
                    if error is not None:
                        raise RuntimeError(
                            "Voice provider initialization failed."
                        ) from error
                    raise RuntimeError(
                        "Voice provider initialization ended before readiness."
                    )
            await asyncio.sleep(0.01)

    try:
        async with asyncio.timeout(timeout_seconds):
            await wait_until_ready()
    except TimeoutError as error:
        raise RuntimeError("Voice provider readiness timed out.") from error


def start_transcriptor(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
    stream_sid: str | None,
    live_turn_runner: LiveVoiceTurnRunner | None = None,
) -> None:
    assert sess.stt_response_queue, "STT response queue must be initialized"
    assert sess.conversation_id, "Conversation must exist before we write transcripts"
    if sess.live_voice_buffer is None:
        raise RuntimeError("Telephony voice buffer is not initialized.")

    session_state = (
        S_ws_manager.get_session_state(
            sess.organization_id,
            sess.auth_session_token,
        )
        if sess.organization_id and sess.auth_session_token
        else None
    )
    live_turn_runner = live_turn_runner or LiveVoiceTurnRunner(
        sess.live_voice_buffer, session_state=session_state
    )
    sess.live_voice_turn_runner = live_turn_runner
    if sess.tts is not None:
        sess.tts.set_turn_outcome_callback(live_turn_runner.record_speech_outcome)

    async def on_interrupt() -> None:
        await live_turn_runner.interrupt()
        if sess.tts_audio_transcoder is not None:
            sess.tts_audio_transcoder.reset()
        logger.info("Triggering telephony interruption for stream %s", stream_sid)
        result = await telephony_manager.handle_interruption(stream_sid or "")
        if result.failure_code:
            logger.warning("Carrier interruption was not delivered.")

    async def on_end_call(
        request_id: UUID,
        final_message: str | None,
    ) -> None:
        await terminate_telephony_voice(
            sess=sess,
            telephony_manager=telephony_manager,
            ended_reason=CallEndedReason.CUSTOMER_ENDED_CALL,
            source=VoiceRequestSource.END_CALL,
            final_message=final_message,
            request_id=request_id,
        )

    sess.stt_tasks["transcriptor"] = asyncio.create_task(
        write_user_transcript(
            sess.stt_response_queue,
            sess.conversation_id,
            sess.tts,
            sess.tts_interrupt_event,
            session_state.speech_activity_event if session_state else None,
            on_interrupt=on_interrupt,
            on_end_call=on_end_call,
            voice_config=sess.voice_config,
            session_state=session_state,
            on_final_transcript=live_turn_runner.submit,
            voice_session_id=sess.call_sid,
            voice_session_row_id=sess.voice_session_id,
            voice_runtime_mode=VoiceRuntimeMode.TELEPHONY,
            live_buffer=sess.live_voice_buffer,
        )
    )
