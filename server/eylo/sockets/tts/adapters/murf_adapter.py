"""Murf AI TTS adapter for the production TTS manager.

Bridges Murf's WebSocket streaming TTS to the interface expected by
TTSRealtime/TTSFactory.

Murf AI provides high-quality TTS with:
- WebSocket streaming for low latency
- Context ID support for conversational continuity
- Native interruption via clear_context protocol
- Voice styles (Conversational, Narration, etc.)

Connection lifecycle:
- connect() establishes WebSocket to wss://api.murf.ai/v1/speech/stream-input
- Sends voice config on first synthesis
- Background receiver loop decodes base64 audio and pushes to response queue
- handle_interruption() sends clear_context + drains queue
"""

import asyncio
import base64
import json
import logging
import uuid
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection

from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.exceptions import TTSConnectionClosed, TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

_DEFAULT_SAMPLE_RATE = 24000
_DEFAULT_FORMAT = "WAV"
_DEFAULT_CHANNEL = "MONO"
_WS_URL = "wss://api.murf.ai/v1/speech/stream-input"

# WAV header is 44 bytes — strip for raw PCM output
_WAV_HEADER_SIZE = 44


class MurfTTSConfig:
    """Configuration for Murf TTS adapter."""

    def __init__(
        self,
        *,
        voice: str,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        format: str = _DEFAULT_FORMAT,
        channel_type: str = _DEFAULT_CHANNEL,
        style: str | None = None,
        rate: int = 0,
        pitch: int = 0,
        variation: int = 1,
        min_buffer_size: int = 60,
        max_buffer_delay_ms: int = 500,
        api_key: str,
        **kwargs,
    ):
        self.voice_id = voice
        self.voice = voice
        self.sample_rate = sample_rate
        self.format = format.upper()
        self.channel_type = channel_type
        self.style = style
        self.rate = rate
        self.pitch = pitch
        self.variation = variation
        self.min_buffer_size = min_buffer_size
        self.max_buffer_delay_ms = max_buffer_delay_ms
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("Murf TTS api_key is required.")


class MurfTTSAdapter(TTSVendorAdapter):
    """Adapter bridging Murf WebSocket TTS to the TTSFactory interface.

    Maintains a persistent WebSocket connection to Murf's streaming endpoint.
    Uses context IDs to track synthesis turns and support native interruption.
    Audio arrives as base64-encoded JSON, with WAV headers stripped for PCM.
    """

    def __init__(self, config: MurfTTSConfig):
        if config.format.upper() not in {"PCM", "WAV"}:
            raise ValueError("Murf TTS must emit PCM or WAV for realtime voice.")
        # Feed the contract config up from the vendor config. getattr with
        # fallbacks because vendor configs disagree — deepgram has no voice,
        # murf calls it voice_id, openai carries no sample_rate. Unset keys
        # are omitted: passing None would override a field default with an
        # invalid value.
        _contract = {
            "model": getattr(config, "model", None),
            "voice": getattr(config, "voice", None)
            or getattr(config, "voice_id", None),
            "sample_rate": getattr(config, "sample_rate", None),
            # WAV headers are removed by the receiver before chunks leave the
            # adapter, so both supported provider formats become raw PCM here.
            "encoding": "pcm_s16le",
        }
        super().__init__(
            TTSConfig(
                vendor="murf",
                **{k: v for k, v in _contract.items() if v is not None},
            )
        )
        self._config = config
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._ws: Optional[ClientConnection] = None
        self._connected = False
        self._recv_task: Optional[asyncio.Task] = None
        self._voice_config_sent = False
        self._active_context_id: Optional[str] = None
        self._first_chunk = True
        self._consecutive_errors = 0

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with query parameters."""
        url = (
            f"{_WS_URL}"
            f"?api-key={self._config.api_key}"
            f"&sample_rate={self._config.sample_rate}"
            f"&channel_type={self._config.channel_type}"
            f"&format={self._config.format}"
        )
        if self._config.min_buffer_size != 60:
            url += f"&min_buffer_size={self._config.min_buffer_size}"
        if self._config.max_buffer_delay_ms != 500:
            url += f"&max_buffer_delay_ms={self._config.max_buffer_delay_ms}"
        return url

    async def connect(self):
        """Connect to Murf TTS WebSocket.

        Raises TTSConnectionFailed if connection cannot be established.
        """
        try:
            url = self._build_ws_url()
            self._ws = await asyncio.wait_for(
                websockets.connect(url),
                timeout=10.0,
            )
            self._connected = True
            self._recv_task = asyncio.create_task(self._receive_loop())
            logger.info(
                "Murf TTS adapter connected (voice=%s, format=%s)",
                self._config.voice_id,
                self._config.format,
            )
            return self
        except asyncio.TimeoutError:
            raise TTSConnectionFailed("Murf TTS: Connection timed out.")
        except Exception as error:
            raise TTSConnectionFailed("Murf TTS: Failed to connect.") from error

    async def _send_voice_config(self):
        """Send voice configuration on first use."""
        if not self._ws or self._voice_config_sent:
            return

        voice_config = {
            "voice_config": {
                "voiceId": self._config.voice_id,
                "rate": self._config.rate,
                "pitch": self._config.pitch,
                "variation": self._config.variation,
            }
        }
        if self._config.style:
            voice_config["voice_config"]["style"] = self._config.style

        await self._ws.send(json.dumps(voice_config))
        self._voice_config_sent = True

    async def _receive_loop(self):
        """Background loop reading audio from Murf WebSocket.

        Murf sends JSON messages with base64-encoded audio.
        WAV headers are stripped for raw PCM output.
        """
        try:
            async for message in self._ws:
                if not self._connected:
                    break

                if not isinstance(message, str):
                    continue

                try:
                    data = json.loads(message)

                    if "audio" in data:
                        audio_bytes = base64.b64decode(data["audio"])

                        # Strip WAV header safely from first audio message
                        if self._config.format == "WAV" and self._first_chunk:
                            skip = min(len(audio_bytes), _WAV_HEADER_SIZE)
                            audio_bytes = audio_bytes[skip:]
                            if skip >= _WAV_HEADER_SIZE:
                                self._first_chunk = False
                            if not audio_bytes:
                                continue

                        try:
                            self._response_queue.put_nowait(audio_bytes)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Murf TTS response queue full, dropping chunk"
                            )
                        self._consecutive_errors = 0

                    elif "error" in data:
                        logger.error("Murf TTS provider error")
                        self._consecutive_errors += 1
                        if self._consecutive_errors >= 3:
                            raise TTSConnectionClosed(
                                f"Murf TTS: {self._consecutive_errors} errors"
                            )

                except json.JSONDecodeError:
                    continue

        except websockets.exceptions.ConnectionClosed:
            logger.info("Murf TTS WebSocket closed")
        except TTSConnectionClosed:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Murf TTS receive loop failed error_type=%s",
                type(error).__name__,
            )

    async def disconnect(self):
        """Close WebSocket connection."""
        self._connected = False

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("Murf TTS adapter disconnected")

    async def send_text(self, text: str) -> None:
        """Send text for synthesis via WebSocket.

        Creates a new context ID for each synthesis request.
        Sends voice config on first use.
        """
        if not self._connected or not self._ws:
            raise TTSConnectionFailed("Not connected. Call connect() first.")
        if not text or not text.strip():
            return

        try:
            # Send voice config on first use
            if not self._voice_config_sent:
                await self._send_voice_config()

            # Generate context ID for this turn
            self._active_context_id = str(uuid.uuid4())
            self._first_chunk = True

            message = {
                "context_id": self._active_context_id,
                "text": text,
                "end": True,
            }

            await self._ws.send(json.dumps(message))
            self._consecutive_errors = 0
        except Exception as error:
            logger.error(
                "Murf TTS send failed error_type=%s",
                type(error).__name__,
            )
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                raise TTSConnectionClosed(
                    f"Murf TTS: {self._consecutive_errors} send failures"
                )

    async def receive_audio(self) -> Optional[bytes]:
        """Get next audio chunk from the response queue."""
        try:
            chunk = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def flush(self) -> None:
        """No explicit flush needed — each request is self-contained with end=True."""
        pass

    async def handle_interruption(self):
        """Send clear_context to cancel synthesis + drain response queue.

        Murf supports native server-side interruption via the clear protocol.
        """
        # Send clear_context to stop server-side synthesis
        if self._ws and self._active_context_id:
            try:
                await self._ws.send(
                    json.dumps(
                        {
                            "context_id": self._active_context_id,
                            "clear": True,
                        }
                    )
                )
            except Exception as error:
                logger.error(
                    "Murf TTS clear context failed error_type=%s",
                    type(error).__name__,
                )

        # Drain response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._active_context_id = None

    async def keepalive(self):
        """Send a ping to keep the WebSocket alive."""
        if self._ws:
            try:
                await self._ws.ping()
            except Exception:
                pass

    @property
    def sample_rate(self) -> int:
        return self._config.sample_rate

    @property
    def provider(self) -> str:
        return "murf"

    @property
    def is_connected(self) -> bool:
        return bool(getattr(self, "_connected", False))

    @property
    def model(self) -> str:
        return str(getattr(self._config, "model", "") or "")

    @property
    def capabilities(self) -> TTSCapabilities:
        """Derived from this adapter's own behaviour, not from memory.

        Confirm a False against vendor documentation before relying on it —
        under-claiming makes a caller skip a feature, over-claiming breaks it.
        """
        return TTSCapabilities(
            streaming=True,
            batch_synthesize=False,
            native_interruption=False,
            aligned_transcript=False,
            emotion_control=False,
            speed_control=True,
            voice_cloning=False,
            context_continuity=False,
        )
