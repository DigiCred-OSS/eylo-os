"""Forward WebSocket audio frames into the active voice pipeline."""

from typing import Optional

from eylo.audio.ops import is_silent
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.voice.browser import handle_audio_config as handle_audio_config
from eylo.pipelines.websocket.handlers.error import handle_error
from eylo.pipelines.websocket.schemas import (
    WsRequestEvent,
    WsResponse,
)

from .log import logger


async def handle_audio_data(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Handle incoming audio data from WebSocket client.

    This function processes audio data received from the WebSocket client,
    sending it to the STT service for transcription. It handles both binary
    audio data and format metadata.

    Args:
        event: The WebSocket event containing audio data

    Returns:
        Response event acknowledging receipt

    """
    if not event.data:
        return await handle_error(event=event, ctx=ctx, message="No audio data payload")

    audio_data = event.data.get("audio_data")

    if not audio_data or not isinstance(audio_data, bytes):
        return await handle_error(
            event=event,
            ctx=ctx,
            message="Expected binary data",
        )

    # Realtime mode: forward directly to vendor adapter
    if ctx.ws.realtime_mode and ctx.ws.realtime_manager:
        await ctx.ws.realtime_manager.send_audio(audio_data)
        return

    # detect if the binary data is all zeros (C-level scan via audio_ops)
    if is_silent(audio_data):
        return
    if len(audio_data) == 0:
        return
    # let's have some threshold for silence
    silence_threshold = 0.01  # Adjust as needed
    if len(audio_data) < silence_threshold * ctx.ws.stt_encoding_info.sample_rate:
        return await handle_error(
            event=event,
            ctx=ctx,
            message="Audio data is too short or silent",
        )

    if not ctx.ws.stt_started or not ctx.ws.stt_socket:
        logger.warning(
            "STT not ready, dropping audio packet, stt_started: %s, stt_socket: %s",
            ctx.ws.stt_started,
            ctx.ws.stt_socket,
        )
        return

    # Non-blocking recording tap (instant bytearray extend)
    if ctx.ws.audio_recorder:
        ctx.ws.audio_recorder.record_user(audio_data)

    await ctx.ws.stt_socket.send_audio(audio_data)
