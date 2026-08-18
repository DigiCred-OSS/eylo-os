"""Voice transcript processing for live audio pipelines.

This module owns the runtime path from STT results to live-only user turns.
Socket handlers and telephony adapters should feed it STT queue items and
transport-specific interruption callbacks; raw buffering, end-call phrase
handling, and TTS interruption policy stay here.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from eylo.common.database import start_transaction
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.voice.schemas.api import (
    ConversationControl,
    InterruptionType,
    StopSpeakingPlan,
    VoiceConfig,
)
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.pipelines.voice.lifecycle_policy import matches_end_call_phrase
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceDraft,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.live_transcript import schedule_live_message_transcripts
from eylo.pipelines.voice.request_state import (
    VoiceRequestSource,
    VoiceRequestStatus,
)
from eylo.pipelines.voice.tts import TTSRealtime
from eylo.pipelines.websocket.schemas import WSSessionState

logger = logging.getLogger(__name__)


async def _handle_tts_interruption(
    tts_manager: TTSRealtime | None,
    tts_interrupt_event: asyncio.Event,
    on_interrupt: Callable[[], Awaitable[None]] | None = None,
) -> None:
    if tts_manager:
        try:
            await tts_manager.interrupt()
            tts_interrupt_event.set()
            logger.info("TTS interruption: Set tts_interrupt_event.")
        except Exception as error:
            logger.error(
                "TTS interruption failed error_type=%s",
                type(error).__name__,
            )
    else:
        logger.debug("Interrupt signal received while TTS is disabled.")

    if on_interrupt:
        try:
            await on_interrupt()
        except Exception as error:
            logger.error(
                "Voice runtime interruption failed error_type=%s",
                type(error).__name__,
            )


async def _buffer_user_transcript(
    conversation_id: UUID,
    transcript: str,
    live_buffer: LiveVoiceBuffer,
    request_id: UUID | None = None,
    voice_session_id: str | None = None,
    voice_session_row_id: UUID | None = None,
    voice_runtime_mode: VoiceRuntimeMode | None = None,
) -> int | None:
    identity = live_buffer.identity
    if identity.conversation_id != conversation_id:
        raise ValueError("Live voice buffer belongs to another conversation.")
    if voice_session_id is not None and identity.session_id != voice_session_id:
        raise ValueError("Live voice buffer belongs to another session.")
    if (
        voice_session_row_id is not None
        and identity.voice_session_id != voice_session_row_id
    ):
        raise ValueError("Live voice buffer belongs to another voice session row.")
    if (
        voice_runtime_mode is not None
        and identity.runtime_mode is not voice_runtime_mode
    ):
        raise ValueError("Live voice buffer belongs to another runtime mode.")

    appended = await live_buffer.append_turn(
        [
            LiveVoiceDraft(
                kind=LiveVoiceItemKind.USER_TRANSCRIPT,
                payload=transcript,
                request_id=request_id,
            )
        ]
    )
    schedule_live_message_transcripts(identity, appended)
    return appended[-1].sequence if appended else None


async def _buffer_tracked_user_transcript(
    conversation_id: UUID,
    transcript: str,
    session_state: WSSessionState | None,
    live_buffer: LiveVoiceBuffer,
    voice_session_id: str | None = None,
    voice_session_row_id: UUID | None = None,
    voice_runtime_mode: VoiceRuntimeMode | None = None,
) -> tuple[UUID, int | None]:
    request_id = uuid4()
    if session_state:
        session_state.start_voice_request(
            request_id=request_id,
            conversation_id=conversation_id,
            source=VoiceRequestSource.USER,
            status=VoiceRequestStatus.USER_TRANSCRIBING,
        )
    captured_sequence = await _buffer_user_transcript(
        conversation_id,
        transcript,
        live_buffer,
        request_id=request_id,
        voice_session_id=voice_session_id,
        voice_session_row_id=voice_session_row_id,
        voice_runtime_mode=voice_runtime_mode,
    )
    if captured_sequence is not None and session_state:
        session_state.mark_voice_request(
            request_id,
            VoiceRequestStatus.LIVE_INPUT_BUFFERED,
        )
    return request_id, captured_sequence


def _track_prebuffered_user_input(
    conversation_id: UUID,
    session_state: WSSessionState | None,
    captured_sequence: int,
) -> tuple[UUID, int]:
    """Correlate an input already captured by transport-specific live control."""
    request_id = uuid4()
    if session_state:
        session_state.start_voice_request(
            request_id=request_id,
            conversation_id=conversation_id,
            source=VoiceRequestSource.USER,
            status=VoiceRequestStatus.LIVE_INPUT_BUFFERED,
        )
    return request_id, captured_sequence


async def _validated_dtmf_sequence(
    metadata: object,
    live_buffer: LiveVoiceBuffer,
) -> int | None:
    if not isinstance(metadata, dict) or metadata.get("source") != "dtmf":
        return None
    sequence = metadata.get("live_buffer_sequence")
    digits = metadata.get("digits")
    if not isinstance(sequence, int) or sequence <= 0 or not isinstance(digits, str):
        return None
    snapshot = await live_buffer.snapshot()
    matched = next(
        (item for item in snapshot.items if item.sequence == sequence),
        None,
    )
    if (
        matched is None
        or matched.kind is not LiveVoiceItemKind.DTMF
        or matched.payload != digits
    ):
        return None
    return sequence


def _should_allow_interruption(
    stop_plan: StopSpeakingPlan,
    effective_interruption_type: InterruptionType,
    result_type: str,
    transcript: str,
    last_interruption_time: float | None,
    vad_should_interrupt: bool = False,
) -> bool:
    normalized_transcript = transcript.strip().lower()

    if last_interruption_time and stop_plan.backoff_seconds > 0:
        elapsed = time.time() - last_interruption_time
        if elapsed < stop_plan.backoff_seconds:
            return False

    if normalized_transcript and any(
        normalized_transcript == phrase.strip().lower()
        for phrase in stop_plan.acknowledgement_phrases
    ):
        return False

    if normalized_transcript and any(
        phrase.strip().lower() in normalized_transcript
        for phrase in stop_plan.interruption_phrases
        if phrase.strip()
    ):
        return True

    if vad_should_interrupt and not transcript:
        return True

    if (
        result_type == "interrupt"
        and not transcript
        and effective_interruption_type == InterruptionType.VAD
    ):
        return True

    word_count = len(transcript.split())
    effective_min_words = stop_plan.num_words
    if (
        effective_min_words == 0
        and effective_interruption_type == InterruptionType.TRANSCRIPT
    ):
        if stop_plan.interruption_sensitivity < 0.34:
            effective_min_words = 3
        elif stop_plan.interruption_sensitivity < 0.67:
            effective_min_words = 1

    if effective_interruption_type == InterruptionType.TRANSCRIPT:
        return word_count >= max(1, effective_min_words)
    return word_count >= effective_min_words


def _get_effective_interruption_type(
    stop_plan: StopSpeakingPlan,
) -> InterruptionType:
    return stop_plan.interruption_type


async def write_user_transcript(
    stt_queue: asyncio.Queue,
    conversation_id: UUID,
    tts_manager: TTSRealtime | None,
    tts_interrupt_event: asyncio.Event,
    speech_activity_event: asyncio.Event | None = None,
    on_interrupt: Callable[[], Awaitable[None]] | None = None,
    on_end_call: (Callable[[UUID, str | None], Awaitable[None]] | None) = None,
    on_final_transcript: (
        Callable[[UUID, str, int | None], Awaitable[None]] | None
    ) = None,
    voice_config: VoiceConfig | None = None,
    session_state: WSSessionState | None = None,
    voice_session_id: str | None = None,
    voice_session_row_id: UUID | None = None,
    voice_runtime_mode: VoiceRuntimeMode | None = None,
    *,
    live_buffer: LiveVoiceBuffer,
) -> None:
    """Process STT results and retain final user transcripts in live memory.

    The queue carries normalized STT events from browser, WebRTC, or telephony
    audio paths. This coroutine applies voice policy around end-call phrases,
    interruption, and request tracking before writing final transcripts to the
    session buffer. No raw turn is written to a message, event, or segment.
    """
    stop_plan = (
        voice_config.stop_speaking_plan
        if voice_config
        else StopSpeakingPlan()
    )
    conversation_control = (
        voice_config.conversation_control if voice_config else ConversationControl()
    )
    end_call_phrases = conversation_control.end_call_phrases
    end_call_message = conversation_control.end_call_message

    last_interruption_time: float | None = None
    effective_interruption_type = _get_effective_interruption_type(stop_plan)

    while True:
        stt_item_acquired = False
        try:
            stt_result = await stt_queue.get()
            stt_item_acquired = True
            result_type = stt_result.get("type", "")

            transcript = stt_result.get("transcript", "")
            is_final_transcript = stt_result.get("is_final", True)
            vad_should_interrupt = bool(stt_result.get("should_interrupt"))
            metadata = stt_result.get("metadata")
            logger.info(
                "Transcript pipeline event type=%s final=%s transcript_chars=%d",
                result_type,
                is_final_transcript,
                len(transcript),
            )

            if (
                result_type == "transcript"
                and transcript
                and is_final_transcript
                and matches_end_call_phrase(transcript, end_call_phrases)
            ):
                logger.info(
                    "End-call phrase detected for conversation %s chars=%d",
                    conversation_id,
                    len(transcript),
                )
                request_id, _ = await _buffer_tracked_user_transcript(
                    conversation_id,
                    transcript,
                    session_state,
                    live_buffer,
                    voice_session_id=voice_session_id,
                    voice_session_row_id=voice_session_row_id,
                    voice_runtime_mode=voice_runtime_mode,
                )
                stt_queue.task_done()
                stt_item_acquired = False
                if on_end_call is None:
                    logger.error(
                        "End-call phrase has no transport termination owner for "
                        "conversation %s; voice remains active.",
                        conversation_id,
                    )
                    continue
                await on_end_call(request_id, end_call_message)
                break

            if (
                transcript or result_type in {"interrupt", "vad"}
            ) and speech_activity_event:
                if session_state:
                    session_state.transport_playback_gate.cancel()
                    session_state.voice_activity_gate.mark_user_activity()
                speech_activity_event.set()

            if result_type in {"interrupt", "vad"} or transcript:
                should_interrupt = _should_allow_interruption(
                    stop_plan,
                    effective_interruption_type,
                    result_type,
                    transcript,
                    last_interruption_time,
                    vad_should_interrupt,
                )
                if should_interrupt:
                    interrupted_request_id = None
                    if tts_manager and tts_manager.is_playback_active():
                        interrupted_request_id = (
                            tts_manager.active_request_id
                            or tts_manager.queued_request_id
                        )
                    if session_state and interrupted_request_id:
                        session_state.mark_voice_request(
                            interrupted_request_id,
                            VoiceRequestStatus.INTERRUPTED,
                        )
                    await _handle_tts_interruption(
                        tts_manager, tts_interrupt_event, on_interrupt
                    )
                    if (
                        interrupted_request_id
                        and session_state
                        and session_state.user_session_id
                        and voice_session_row_id
                    ):
                        try:
                            async with start_transaction() as db_session:
                                await file_user_session_fact(
                                    db_session,
                                    organization_id=session_state.organization_id,
                                    user_session_id=session_state.user_session_id,
                                    subject_type="voice.session",
                                    subject_id=voice_session_row_id,
                                    event_type="voice.user.interrupted_agent",
                                    payload={
                                        "conversation_id": str(conversation_id),
                                        "request_id": interrupted_request_id,
                                    },
                                )
                        except Exception as error:
                            logger.error(
                                "Voice interruption fact failed error_type=%s",
                                type(error).__name__,
                            )
                    last_interruption_time = time.time()

            if result_type == "transcript" and transcript and is_final_transcript:
                live_buffer_sequence = await _validated_dtmf_sequence(
                    metadata,
                    live_buffer,
                )
                if live_buffer_sequence is not None:
                    request_id, captured_sequence = _track_prebuffered_user_input(
                        conversation_id,
                        session_state,
                        live_buffer_sequence,
                    )
                else:
                    (
                        request_id,
                        captured_sequence,
                    ) = await _buffer_tracked_user_transcript(
                        conversation_id,
                        transcript,
                        session_state,
                        live_buffer,
                        voice_session_id=voice_session_id,
                        voice_session_row_id=voice_session_row_id,
                        voice_runtime_mode=voice_runtime_mode,
                    )
                if on_final_transcript is not None:
                    await on_final_transcript(
                        request_id,
                        transcript,
                        captured_sequence,
                    )

            stt_queue.task_done()
            stt_item_acquired = False

        except asyncio.CancelledError:
            if stt_item_acquired:
                stt_queue.task_done()
            logger.info("User transcript writer task cancelled")
            break
        except Exception as error:
            if stt_item_acquired:
                stt_queue.task_done()
            logger.error(
                "Transcript pipeline failed error_type=%s",
                type(error).__name__,
            )
