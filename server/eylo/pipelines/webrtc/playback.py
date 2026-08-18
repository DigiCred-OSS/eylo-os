"""WebRTC playback queue bridging for browser voice sessions."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import arrow

from eylo.pipelines.websocket.schemas import SessionUUID, WSSessionState

logger = logging.getLogger(__name__)


def enqueue_tts_chunk(session_state: WSSessionState, audio_chunk: bytes) -> None:
    """Enqueue audio for the outgoing WebRTC track, dropping oldest on pressure."""
    queue = session_state.tts_response_queue
    if queue is None:
        return

    try:
        queue.put_nowait(audio_chunk)
    except asyncio.QueueFull:
        logger.warning(
            "[STREAM_TTS] TTS response queue full (size=%s), dropping oldest chunk. "
            "Chunk size: %s bytes",
            queue.qsize(),
            len(audio_chunk),
        )
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            return
        try:
            queue.put_nowait(audio_chunk)
        except asyncio.QueueFull:
            logger.error("[STREAM_TTS] Unable to enqueue audio even after drop")
            return

    session_state.last_activity_at = arrow.utcnow().timestamp()


def needs_tts_streamer(session_state: WSSessionState) -> bool:
    """Return true when TTS manager output must bridge to WebRTC playback queue."""
    tts_manager = session_state.tts_manager
    if not tts_manager or session_state.tts_response_queue is None:
        return False
    return tts_manager.consumer_queue is not session_state.tts_response_queue


def start_tts_streamer(
    *,
    organization_id: UUID,
    session_id: SessionUUID,
) -> asyncio.Task[None]:
    """Start a background task that bridges TTS manager audio to WebRTC playback."""
    return asyncio.create_task(
        stream_tts_to_peer(
            organization_id=organization_id,
            session_id=session_id,
        )
    )


async def stop_tts_streamer(
    task: asyncio.Task[None] | None,
    *,
    session_id: SessionUUID,
) -> None:
    """Cancel the WebRTC TTS streamer task owned by this playback pipeline."""
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("TTS streamer task cancelled")


async def stream_tts_to_peer(
    *,
    organization_id: UUID,
    session_id: SessionUUID,
) -> None:
    """Bridge TTS manager consumer audio into the outgoing WebRTC track queue."""
    from eylo.pipelines.websocket.singleton import S_ws_manager

    logger.info("[STREAM_TTS] Starting TTS audio streamer for peer...")
    total_bytes_sent = 0
    try:
        logger.info("TTSAudioStreamer: task started.")
        while True:
            current_session_state = S_ws_manager.get_session_state(
                organization_id,
                session_id,
            )

            if not current_session_state:
                logger.info("TTSAudioStreamer: Session state not found, exiting.")
                break

            if not current_session_state.tts_manager:
                logger.warning("TTSAudioStreamer: TTS manager not found, retrying...")
                await asyncio.sleep(0.1)
                continue

            tts_manager = current_session_state.tts_manager
            tts_queue = tts_manager.consumer_queue
            audio_chunk = await tts_queue.get()

            if audio_chunk is None:
                logger.info(
                    "[STREAM_TTS] End-of-stream marker received, shutting down."
                )
                break

            if audio_chunk:
                total_bytes_sent += len(audio_chunk)
                logger.debug(
                    "[TTS_PIPELINE] consumer_queue -> tts_response_queue: %s bytes "
                    "(total: %s)",
                    len(audio_chunk),
                    total_bytes_sent,
                )
                if current_session_state.tts_response_queue:
                    enqueue_tts_chunk(current_session_state, audio_chunk)

            tts_queue.task_done()

    except asyncio.CancelledError:
        logger.info(
            "[STREAM_TTS] TTS audio streamer is shutting down due to cancellation."
        )
    except Exception as error:
        logger.error(
            "TTS audio streamer failed error_type=%s",
            type(error).__name__,
        )
