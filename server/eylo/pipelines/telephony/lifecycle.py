"""Telephony call lifecycle pipeline helpers.

The socket route owns provider WebSocket receive/close mechanics. This module
owns provider-independent runtime lifecycle work: call events, DTMF transcript
injection, outbound TTS queue production, and call-session finalization.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import arrow

from eylo.common.database import start_transaction
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.call import (
    CallConnectedEvent,
    CallDirection,
    CallEndedEvent,
    CallStartedEvent,
    CallTransferredEvent,
)
from eylo.modules.telephony.lifecycle import (
    record_call_started,
    record_call_status,
    record_call_transfer_completed,
)
from eylo.modules.telephony.schemas import CallStatus
from eylo.modules.user_sessions.domain import UserSessionState
from eylo.modules.user_sessions.service import UserSessionService
from eylo.modules.voice_transcripts.constants import (
    VoiceRuntimeMode,
    VoiceSessionStatus,
)
from eylo.modules.voice_transcripts.lifecycle import record_voice_session_ended
from eylo.pipelines.session_timeline import try_file_runtime_fact
from eylo.pipelines.telephony.sessions import S_CALLS, CallSession
from eylo.pipelines.telephony.voice import collect_call_audio_metrics
from eylo.pipelines.voice.audio_transport import ComfortAudioStream
from eylo.pipelines.voice.live_buffer import LiveVoiceDraft, LiveVoiceItemKind
from eylo.pipelines.voice.post_call import finalize_live_voice_history
from eylo.pipelines.websocket.singleton import S_ws_manager
from eylo.runtime.tasks import teardown_queues
from eylo.sockets.telephony.base import CallEndedReason, InboundMediaMessage
from eylo.sockets.telephony.dtmf import DTMFCollector
from eylo.sockets.telephony.manager import TelephonyRealtime

logger = logging.getLogger(__name__)


def call_event_kwargs(sess: CallSession, provider: str) -> dict:
    """Build common kwargs for call lifecycle events from a call session."""
    if not sess.provider_config_id or not sess.provider_config_revision:
        raise ValueError("Call session is missing pinned telephony authority.")
    if sess.provider and sess.provider != provider:
        raise ValueError("Call session provider does not match runtime provider.")
    return {
        "call_sid": sess.call_sid,
        "session_id": sess.auth_session_token or sess.stream_sid or sess.call_sid,
        "organization_id": sess.organization_id,
        "conversation_id": sess.conversation_id,
        "direction": CallDirection(sess.direction)
        if sess.direction
        else CallDirection.INBOUND,
        "provider": provider,
        "provider_config_id": sess.provider_config_id,
        "provider_config_revision": sess.provider_config_revision,
        "from_number": sess.from_number,
        "to_number": sess.to_number,
        "agent_id": sess.agent_id,
        "agent_revision": sess.agent_revision,
        "data": sess.extra_data,
    }


async def emit_call_started(sess: CallSession, provider: str) -> bool:
    if not sess.organization_id:
        return False
    event = CallStartedEvent(
        message="Call started",
        **call_event_kwargs(sess, provider),
    )
    try:
        call = await record_call_started(
            organization_id=event.organization_id,
            call_sid=event.call_sid,
            provider=event.provider,
            provider_config_id=event.provider_config_id,
            provider_config_revision=event.provider_config_revision,
            direction=event.direction.value,
            from_number=event.from_number,
            to_number=event.to_number,
            agent_id=event.agent_id,
            agent_revision=event.agent_revision,
            conversation_id=event.conversation_id,
            user_session_id=sess.user_session_id,
            campaign_id=_event_uuid(event.data, "campaign_id"),
            campaign_contact_id=_event_uuid(event.data, "campaign_contact_id"),
            campaign_attempt_id=_event_uuid(event.data, "campaign_attempt_id"),
        )
        sess.call_id = call.id
    except Exception:
        logger.error("Could not persist call start for %s.", event.call_sid)
        return False
    emit_ephemeral(event)
    return True


async def handle_inbound_dtmf(
    *,
    sess: CallSession,
    collector: DTMFCollector,
    digits: str,
) -> None:
    """Collect provider DTMF and inject completed sequences as user text."""
    result = collector.collect(digits)
    if not result or not result.digits:
        return

    captured_sequence: int | None = None
    if sess.live_voice_buffer is None:
        logger.error("DTMF live buffer is unavailable for call %s.", sess.call_sid)
    else:
        try:
            appended = await sess.live_voice_buffer.append_turn(
                [
                    LiveVoiceDraft(
                        kind=LiveVoiceItemKind.DTMF,
                        payload=result.digits,
                    )
                ]
            )
        except Exception as error:
            logger.error(
                "DTMF raw capture failed for call %s (%s).",
                sess.call_sid,
                type(error).__name__,
            )
        else:
            if appended:
                captured_sequence = appended[-1].sequence
            else:
                logger.warning(
                    "DTMF raw capture is incomplete for call %s.",
                    sess.call_sid,
                )

    if sess.stt_response_queue:
        await sess.stt_response_queue.put(
            {
                "type": "transcript",
                "transcript": f"DTMF digits: {result.digits}",
                "is_final": True,
                "metadata": {
                    "source": "dtmf",
                    "digits": result.digits,
                    "completed_by": result.completed_by,
                    "live_buffer_sequence": captured_sequence,
                },
            }
        )


async def handle_media_packet(
    *,
    sess: CallSession,
    media_message: InboundMediaMessage,
    provider: str,
) -> None:
    """Forward inbound call audio to STT and emit first-media lifecycle events."""
    stt_socket = sess.stt
    if not stt_socket or not stt_socket.is_connected:
        raise RuntimeError("Inbound media arrived before STT readiness.")

    if not sess.first_media_received:
        logger.debug("[%s] Received first media packet", provider.upper())
        sess.first_media_received = True
        sess.connected_at = arrow.utcnow().datetime

        if sess.organization_id:
            event = CallConnectedEvent(
                message="Call connected, media active",
                **call_event_kwargs(sess, provider),
            )
            try:
                update = await record_call_status(
                    organization_id=event.organization_id,
                    call_sid=event.call_sid,
                    status=CallStatus.IN_PROGRESS,
                    connected_at=sess.connected_at,
                    conversation_id=event.conversation_id,
                )
            except Exception:
                logger.error("Could not persist connected call %s.", event.call_sid)
            else:
                if not update.update.ignored:
                    emit_ephemeral(event)

    if sess.audio_recorder:
        sess.audio_recorder.record_user(media_message.payload)

    await stt_socket.send_audio(media_message.payload)


async def tts_producer_task(
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
) -> None:
    """Send synthesized audio to the carrier and expose every write failure."""
    if (
        not sess
        or not sess.tts_response_queue
        or not sess.organization_id
        or not sess.tts_audio_transcoder
    ):
        raise RuntimeError("TTS carrier producer is missing session state.")

    comfort_audio, session_state = _telephony_comfort_audio(sess)
    logger.info("Starting TTS producer task for call_sid=%s", sess.call_sid)
    try:
        while True:
            try:
                audio_chunk = await asyncio.wait_for(
                    sess.tts_response_queue.get(),
                    timeout=0.02,
                )
            except asyncio.TimeoutError:
                if (
                    comfort_audio is not None
                    and session_state is not None
                    and session_state.is_agent_thinking
                    and not sess.termination_requested
                ):
                    await _send_carrier_audio(
                        sess=sess,
                        telephony_manager=telephony_manager,
                        audio=comfort_audio.next_frame(),
                        comfort=True,
                    )
                continue
            try:
                if audio_chunk:
                    carrier_audio = sess.tts_audio_transcoder.process(audio_chunk)
                    if not carrier_audio:
                        continue
                    await _send_carrier_audio(
                        sess=sess,
                        telephony_manager=telephony_manager,
                        audio=carrier_audio,
                        comfort=False,
                    )
            finally:
                sess.tts_response_queue.task_done()
    except asyncio.CancelledError:
        logger.info(
            {"message": "TTS producer task cancelled", "call_sid": sess.call_sid}
        )
        raise
    except Exception:
        if sess.ended_reason is None:
            sess.ended_reason = CallEndedReason.ERROR_TTS_FAILED
        raise


def _telephony_comfort_audio(sess: CallSession):
    if not sess.organization_id or not sess.auth_session_token:
        return None, None
    session_state = S_ws_manager.get_session_state(
        sess.organization_id,
        sess.auth_session_token,
    )
    config = getattr(session_state, "ambient_noise_config", None)
    if not config or not bool(config.get("enabled", True)):
        return None, session_state
    if sess.tts_audio_transcoder is None:
        return None, session_state
    amplitude = int(config.get("amplitude", 50))
    if amplitude <= 0:
        return None, session_state
    return (
        ComfortAudioStream(
            target=sess.tts_audio_transcoder.target,
            amplitude=amplitude,
            enabled=True,
        ),
        session_state,
    )


async def _send_carrier_audio(
    *,
    sess: CallSession,
    telephony_manager: TelephonyRealtime,
    audio: bytes,
    comfort: bool,
) -> None:
    result = await telephony_manager.send_audio(audio, sess.stream_sid or "")
    if not result.accepted:
        sess.ended_reason = CallEndedReason.ERROR_PROVIDER_DISCONNECTED
        raise RuntimeError(result.failure_code or "carrier_audio_write_failed")
    sess.carrier_audio_chunks += 1
    sess.carrier_audio_bytes += result.bytes_count
    if comfort:
        sess.comfort_audio_chunks += 1
        sess.comfort_audio_bytes += result.bytes_count
    if sess.audio_recorder is not None:
        try:
            sess.audio_recorder.record_agent(audio)
        except Exception:
            logger.error(
                "Agent audio recording failed for call %s; carrier playback continues.",
                sess.call_sid,
            )


async def finalize_call_session(
    *,
    sess: CallSession,
    provider: str,
    auth_session_token: str | None,
) -> bool:
    """Finalize exactly once; registry cleanup survives every inner failure."""
    async with sess.finalization_lock:
        if sess.finalized:
            return sess.manager_closed_ws
        completed = False
        try:
            sess.manager_closed_ws = await _finalize_call_session_once(
                sess=sess,
                provider=provider,
                auth_session_token=auth_session_token,
            )
            completed = True
            return sess.manager_closed_ws
        finally:
            sess.finalized = completed
            S_CALLS.remove(sess)


async def _finalize_call_session_once(
    *,
    sess: CallSession,
    provider: str,
    auth_session_token: str | None,
) -> bool:
    """Persist terminal state, then contain every secondary cleanup failure."""
    sess.is_active = False
    _resolve_final_ended_reason(sess)

    duration_seconds = _duration_seconds(sess)
    terminal_status = map_ended_reason_to_status(sess.ended_reason)

    logger.info(
        {
            "message": "Call ended",
            "call_sid": sess.call_sid,
            "ended_reason": sess.ended_reason.value,
            "terminal_status": terminal_status,
            "duration_seconds": duration_seconds,
        }
    )

    terminal_error: Exception | None = None
    call_audio_metrics: dict = {}
    if sess.organization_id:
        try:
            call_audio_metrics = collect_call_audio_metrics(sess)
        except Exception:
            call_audio_metrics = {}
            logger.error("Could not collect call audio metrics.")
        call_audio_metrics["termination_reason"] = sess.ended_reason.value
        ended_event = CallEndedEvent(
            message=f"Call ended: {sess.ended_reason.value}",
            ended_reason=sess.ended_reason.value,
            terminal_status=terminal_status,
            duration_seconds=duration_seconds,
            **call_event_kwargs(sess, provider),
        )
        try:
            update = await record_call_status(
                organization_id=ended_event.organization_id,
                call_sid=ended_event.call_sid,
                status=terminal_status,
                ended_reason=ended_event.ended_reason,
                ended_at=arrow.utcnow().datetime,
                duration_seconds=int(duration_seconds)
                if duration_seconds is not None
                else None,
                conversation_id=ended_event.conversation_id,
                source="media_runtime",
            )
        except Exception as error:
            terminal_error = error
            logger.error("Could not persist ended call %s.", ended_event.call_sid)
        else:
            canonical_status = (
                (
                    update.update.call.status.value
                    if isinstance(update.update.call.status, CallStatus)
                    else str(update.update.call.status)
                )
                if update.update.call is not None
                else None
            )
            if not update.update.ignored and canonical_status == terminal_status:
                emit_ephemeral(ended_event)
        await _persist_transfer_completion(sess, provider)
        logger.info(
            "Telephony voice runtime ended for call_sid=%s metrics=%s",
            sess.call_sid,
            call_audio_metrics,
        )
        await asyncio.sleep(0)

    await _settle_pending_opener(sess)
    try:
        await _finalize_recording(sess)
    except Exception:
        logger.error("Could not finalize call recording for %s.", sess.call_sid)
    try:
        await _drain_voice_pipeline(sess)
    except Exception:
        logger.error("Could not drain voice runtime for %s.", sess.call_sid)
    voice_ended_at = arrow.utcnow().datetime
    if sess.live_voice_buffer is not None:
        try:
            await finalize_live_voice_history(sess.live_voice_buffer)
        except Exception as error:
            logger.error(
                "Could not project canonical telephony voice history error_type=%s",
                type(error).__name__,
            )
    if sess.organization_id and sess.voice_session_id is not None:
        try:
            await record_voice_session_ended(
                organization_id=sess.organization_id,
                voice_session_id=sess.voice_session_id,
                runtime_mode=VoiceRuntimeMode.TELEPHONY,
                ended_at=voice_ended_at,
                ended_reason=sess.ended_reason.value,
                status=(
                    VoiceSessionStatus.FAILED
                    if terminal_status == CallStatus.FAILED
                    else VoiceSessionStatus.COMPLETED
                ),
                duration_ms=int(duration_seconds * 1000)
                if duration_seconds is not None
                else None,
                metrics=call_audio_metrics or None,
            )
        except Exception:
            logger.error(
                "Could not persist telephony voice session completion for %s.",
                sess.voice_session_id,
            )
    if sess.live_voice_buffer is not None:
        try:
            await sess.live_voice_buffer.discard()
        except Exception as error:
            logger.error(
                "Could not discard live voice data for %s (%s).",
                sess.call_sid,
                type(error).__name__,
            )
        finally:
            sess.live_voice_buffer = None

    failed_provider = {
        CallEndedReason.ERROR_STT_FAILED: "stt",
        CallEndedReason.ERROR_TTS_FAILED: "tts",
    }.get(sess.ended_reason)
    if failed_provider and sess.organization_id:
        await try_file_runtime_fact(
            organization_id=sess.organization_id,
            user_session_id=sess.user_session_id,
            subject_type=f"provider.{failed_provider}",
            subject_id=sess.voice_session_id,
            event_type=f"provider.{failed_provider}.failed",
            payload={"provider_kind": failed_provider},
        )
    if sess.organization_id:
        for provider_kind in ("stt", "tts"):
            await try_file_runtime_fact(
                organization_id=sess.organization_id,
                user_session_id=sess.user_session_id,
                subject_type=f"provider.{provider_kind}",
                subject_id=sess.voice_session_id,
                event_type=f"provider.{provider_kind}.disconnected",
                payload={"provider_kind": provider_kind},
            )

    if sess.organization_id and sess.user_session_id is not None:
        try:
            async with start_transaction() as db_session:
                await UserSessionService(db_session).finish(
                    organization_id=sess.organization_id,
                    user_session_id=sess.user_session_id,
                    state=(
                        UserSessionState.FAILED
                        if terminal_status == CallStatus.FAILED
                        else UserSessionState.ENDED
                    ),
                    reason=sess.ended_reason.value,
                )
        except Exception as error:
            terminal_error = terminal_error or error
            logger.error(
                "Could not persist terminal user session %s.",
                sess.user_session_id,
            )

    manager_closed_ws = False
    if auth_session_token and sess.organization_id:
        manager_closed_ws = await S_ws_manager.disconnect(
            organization_id=sess.organization_id,
            session_id=auth_session_token,
        )

    if terminal_error is not None:
        raise RuntimeError(
            "Terminal call state could not be persisted."
        ) from terminal_error
    return manager_closed_ws


async def _persist_transfer_completion(sess: CallSession, provider: str) -> None:
    if (
        sess.organization_id is None
        or sess.ended_reason != CallEndedReason.AGENT_FORWARDED_CALL
    ):
        return
    event = CallTransferredEvent(
        message="Call transfer completed",
        transfer_to=sess.extra_data.get("transfer_to") or "",
        **call_event_kwargs(sess, provider),
    )
    try:
        await record_call_transfer_completed(
            organization_id=event.organization_id,
            call_sid=event.call_sid,
            transfer_to=event.transfer_to or None,
            metadata=event.data,
        )
    except Exception:
        logger.error(
            "Could not persist call transfer completion for %s.",
            event.call_sid,
        )
    else:
        emit_ephemeral(event)


async def _settle_pending_opener(sess: CallSession) -> None:
    task = sess.tts_tasks.get("opener_delivery")
    if task is None or task.done():
        if task is not None and not task.cancelled():
            try:
                task.result()
            except Exception:
                logger.error("Outbound opener projection failed.")
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    if sess.call_id is None or sess.organization_id is None:
        return
    from eylo.modules.telephony.lifecycle import record_opener_delivery

    try:
        await record_opener_delivery(
            call_id=sess.call_id,
            organization_id=sess.organization_id,
            accepted=False,
        )
    except Exception:
        logger.error("Pending outbound opener could not be marked failed.")


async def _drain_voice_pipeline(sess: CallSession) -> None:
    if sess.stt:
        try:
            await sess.stt.disconnect()
        except Exception:
            logger.error("STT disconnect failed for %s.", sess.call_sid)
    stt_queues_to_drain = [
        queue for queue in [sess.stt_response_queue, sess.stt_request_queue] if queue
    ]
    if stt_queues_to_drain:
        try:
            await teardown_queues(stt_queues_to_drain, join_timeout=5)
        except Exception:
            logger.error("STT queue drain failed for %s.", sess.call_sid)

    if sess.live_voice_turn_runner is not None:
        try:
            await sess.live_voice_turn_runner.drain()
        except Exception:
            logger.error("Live voice turn drain failed for %s.", sess.call_sid)
        finally:
            sess.live_voice_turn_runner = None

    if sess.tts:
        try:
            await sess.tts.wait_until_done(timeout=5.0)
        except Exception:
            logger.error("TTS completion wait failed for %s.", sess.call_sid)
    tts_queues_to_drain = [
        queue for queue in [sess.tts_response_queue, sess.tts_request_queue] if queue
    ]
    if tts_queues_to_drain:
        try:
            await teardown_queues(tts_queues_to_drain, join_timeout=5)
        except Exception:
            logger.error("TTS queue drain failed for %s.", sess.call_sid)

    all_tasks = (
        list(sess.stt_tasks.values())
        + list(sess.tts_tasks.values())
        + list(sess.policy_tasks.values())
    )
    for task in all_tasks:
        if not task.done():
            task.cancel()
    if all_tasks:
        await asyncio.gather(*all_tasks, return_exceptions=True)
    if sess.tts:
        try:
            await sess.tts.disconnect()
        except Exception:
            logger.error("TTS disconnect failed for %s.", sess.call_sid)


async def _finalize_recording(sess: CallSession) -> None:
    if not sess.audio_recorder:
        return
    await sess.audio_recorder.finalize()
    sess.audio_recorder = None


def _resolve_final_ended_reason(sess: CallSession) -> None:
    if sess.ended_reason in (None, CallEndedReason.ERROR_SYSTEM):
        refined = refine_ended_reason_from_tasks(sess)
        if refined:
            sess.ended_reason = refined
    if sess.ended_reason is None:
        sess.ended_reason = CallEndedReason.UNKNOWN


def refine_ended_reason_from_tasks(sess: CallSession) -> CallEndedReason | None:
    """Upgrade generic system errors when an STT/TTS task failed."""
    stt_failed = _has_failed_task(sess.stt_tasks)
    tts_failed = _has_failed_task(sess.tts_tasks)

    if stt_failed and tts_failed:
        return CallEndedReason.ERROR_SYSTEM
    if stt_failed:
        return CallEndedReason.ERROR_STT_FAILED
    if tts_failed:
        return CallEndedReason.ERROR_TTS_FAILED

    return None


def _has_failed_task(tasks: dict[str, asyncio.Task]) -> bool:
    for name, task in tasks.items():
        if task.done() and not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger.debug("Telephony task '%s' failed.", name)
                return True
    return False


_ENDED_REASON_TO_STATUS: dict[CallEndedReason, str] = {
    CallEndedReason.CUSTOMER_BUSY: CallStatus.BUSY,
    CallEndedReason.CUSTOMER_DID_NOT_ANSWER: CallStatus.NO_ANSWER,
    CallEndedReason.MANUALLY_CANCELED: CallStatus.CANCELED,
    CallEndedReason.ERROR_SYSTEM: CallStatus.FAILED,
    CallEndedReason.ERROR_PROVIDER_DISCONNECTED: CallStatus.FAILED,
    CallEndedReason.ERROR_STT_FAILED: CallStatus.FAILED,
    CallEndedReason.ERROR_TTS_FAILED: CallStatus.FAILED,
    CallEndedReason.ERROR_LLM_FAILED: CallStatus.FAILED,
    CallEndedReason.UNKNOWN: CallStatus.FAILED,
}


def map_ended_reason_to_status(ended_reason: CallEndedReason) -> str:
    """Map a CallEndedReason to the terminal CallStatus for DB persistence."""
    return _ENDED_REASON_TO_STATUS.get(ended_reason, CallStatus.COMPLETED)


def _duration_seconds(sess: CallSession) -> float | None:
    if not sess.started_at:
        return None
    return (arrow.utcnow().datetime - sess.started_at).total_seconds()


def _event_uuid(data: dict, key: str) -> UUID | None:
    value = data.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        logger.warning("Call event has invalid %s metadata.", key)
        return None
