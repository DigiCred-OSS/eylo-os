"""Hume AI TTS adapter for the production TTS manager.

Bridges Hume's Octave WebSocket streaming TTS to the interface expected
by TTSRealtime/TTSFactory.

Hume Octave is an emotionally intelligent TTS system that understands
text both emotionally and semantically. Supports voice design via prompting,
multi-lingual output, and ultra-low latency streaming (~100ms).

Connection lifecycle:
- connect() establishes WebSocket to wss://api.hume.ai/v0/tts/stream/input
- Background receiver loop decodes base64 audio and pushes to response queue
- handle_interruption() drains the queue
"""

import asyncio
import base64
import json
import logging
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection

from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.exceptions import TTSConnectionClosed, TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

_DEFAULT_SPEED = 1.0
_DEFAULT_FORMAT = "pcm"
_DEFAULT_SAMPLE_RATE = 24000
_WS_URL = "wss://api.hume.ai/v0/tts/stream/input"


class HumeTTSConfig:
    """Configuration for Hume TTS adapter."""

    def __init__(
        self,
        *,
        model: str,
        voice: str | None = None,
        voice_description: str | None = None,
        language: str,
        speed: float = _DEFAULT_SPEED,
        format: str = _DEFAULT_FORMAT,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        instant_mode: bool = True,
        api_key: str,
        **kwargs,
    ):
        self.model = model
        self.voice = voice
        self.voice_description = voice_description
        self.language = language
        self.speed = speed
        self.format = format
        self.sample_rate = sample_rate
        self.instant_mode = instant_mode
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("Hume TTS api_key is required.")


class HumeTTSAdapter(TTSVendorAdapter):
    """Adapter bridging Hume Octave WebSocket TTS to the TTSFactory interface.

    Maintains a persistent WebSocket connection to Hume's streaming endpoint.
    Text is sent as utterance messages with voice/model config.
    Audio arrives as base64-encoded JSON messages.
    """

    def __init__(self, config: HumeTTSConfig):
        if config.format.lower() != "pcm":
            raise ValueError("Hume TTS must emit PCM for realtime voice.")
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
            "encoding": "pcm_s16le",
        }
        super().__init__(
            TTSConfig(
                vendor="hume",
                **{k: v for k, v in _contract.items() if v is not None},
            )
        )
        self._config = config
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._ws: Optional[ClientConnection] = None
        self._connected = False
        self._recv_task: Optional[asyncio.Task] = None
        self._consecutive_errors = 0

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with API key auth."""
        return f"{_WS_URL}?api_key={self._config.api_key}"

    async def connect(self):
        """Connect to Hume TTS WebSocket.

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
                "Hume TTS adapter connected (model=%s, voice=%s)",
                self._config.model,
                self._config.voice or self._config.voice_description,
            )
            return self
        except asyncio.TimeoutError:
            raise TTSConnectionFailed("Hume TTS: Connection timed out.")
        except Exception as error:
            raise TTSConnectionFailed("Hume TTS: Failed to connect.") from error

    async def _receive_loop(self):
        """Background loop reading audio from Hume WebSocket.

        Hume sends JSON messages with base64-encoded audio in the 'audio' field.
        """
        try:
            async for message in self._ws:
                if not self._connected:
                    break

                if not isinstance(message, str):
                    continue

                try:
                    data = json.loads(message)

                    # Handle error messages
                    if "error" in data:
                        logger.error("Hume TTS provider error")
                        self._consecutive_errors += 1
                        if self._consecutive_errors >= 3:
                            raise TTSConnectionClosed(
                                f"Hume TTS: {self._consecutive_errors} errors"
                            )
                        continue

                    # Handle audio
                    if "audio" in data:
                        audio_bytes = base64.b64decode(data["audio"])
                        try:
                            self._response_queue.put_nowait(audio_bytes)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Hume TTS response queue full, dropping chunk"
                            )
                        self._consecutive_errors = 0

                except json.JSONDecodeError:
                    continue

        except websockets.exceptions.ConnectionClosed:
            logger.info("Hume TTS WebSocket closed")
        except TTSConnectionClosed:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Hume TTS receive loop failed error_type=%s",
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

        logger.info("Hume TTS adapter disconnected")

    async def send_text(self, text: str) -> None:
        """Send text for synthesis via WebSocket.

        Constructs Hume's utterance message format with voice and model config.
        """
        if not self._connected or not self._ws:
            raise TTSConnectionFailed("Not connected. Call connect() first.")
        if not text or not text.strip():
            return

        try:
            # Build utterance
            utterance = {
                "type": "utterance",
                "text": text,
                "language": self._config.language,
                "speed": self._config.speed,
            }

            # Voice config
            if self._config.voice:
                utterance["voice"] = {"name": self._config.voice}
            elif self._config.voice_description:
                utterance["voice"] = {"description": self._config.voice_description}

            message = {
                "model": self._config.model,
                "format": self._config.format,
                "instant_mode": self._config.instant_mode,
                "utterances": [utterance],
            }

            await self._ws.send(json.dumps(message))
            self._consecutive_errors = 0
        except Exception as error:
            logger.error(
                "Hume TTS send failed error_type=%s",
                type(error).__name__,
            )
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                raise TTSConnectionClosed(
                    f"Hume TTS: {self._consecutive_errors} send failures"
                )

    async def receive_audio(self) -> Optional[bytes]:
        """Get next audio chunk from the response queue."""
        try:
            chunk = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def flush(self) -> None:
        """No explicit flush protocol for Hume — each utterance is self-contained."""
        pass

    async def handle_interruption(self):
        """Drain response queue to stop playback."""
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

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
        return "hume"

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
