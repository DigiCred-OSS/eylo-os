"""Smallest AI TTS adapter for the production TTS manager.

Bridges Smallest AI's Lightning-v2 WebSocket streaming to the interface
expected by TTSRealtime/TTSFactory.

Smallest AI provides ultra-low latency TTS (~50-80ms) via persistent
WebSocket connection. Audio is delivered as binary frames or base64 JSON.

Connection lifecycle:
- connect() establishes WebSocket to wss://waves-api.smallest.ai
- Background receiver loop pushes audio to response queue
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

_DEFAULT_SAMPLE_RATE = 24000
_WS_URL = "wss://waves-api.smallest.ai/api/v1/lightning-v2/get_speech/stream?timeout=60"


class SmallestTTSConfig:
    """Configuration for Smallest AI TTS adapter."""

    def __init__(
        self,
        *,
        voice: str,
        model: str,
        language: str,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        add_wav_header: bool = False,
        api_key: str,
        **kwargs,
    ):
        self.voice_id = voice
        self.voice = voice
        self.model = model
        self.language = language
        self.sample_rate = sample_rate
        self.add_wav_header = add_wav_header
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("Smallest TTS api_key is required.")


class SmallestTTSAdapter(TTSVendorAdapter):
    """Adapter bridging Smallest AI WebSocket TTS to the TTSFactory interface.

    Maintains a persistent WebSocket connection to Smallest's streaming endpoint.
    Text is sent as JSON with voice/language config per message.
    Audio arrives as binary frames or base64-encoded JSON.
    """

    def __init__(self, config: SmallestTTSConfig):
        if config.add_wav_header:
            raise ValueError(
                "Smallest TTS add_wav_header must be false for realtime voice."
            )
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
                vendor="smallest",
                **{k: v for k, v in _contract.items() if v is not None},
            )
        )
        self._config = config
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._ws: Optional[ClientConnection] = None
        self._connected = False
        self._recv_task: Optional[asyncio.Task] = None
        self._consecutive_errors = 0

    async def connect(self):
        """Connect to Smallest AI TTS WebSocket.

        Raises TTSConnectionFailed if connection cannot be established.
        """
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    _WS_URL,
                    additional_headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                    },
                ),
                timeout=10.0,
            )
            self._connected = True
            self._recv_task = asyncio.create_task(self._receive_loop())
            logger.info(
                "Smallest TTS adapter connected (voice=%s, lang=%s)",
                self._config.voice_id,
                self._config.language,
            )
            return self
        except asyncio.TimeoutError:
            raise TTSConnectionFailed("Smallest TTS: Connection timed out.")
        except Exception as error:
            raise TTSConnectionFailed("Smallest TTS: Failed to connect.") from error

    async def _receive_loop(self):
        """Background loop reading audio frames from Smallest WebSocket."""
        try:
            async for message in self._ws:
                if not self._connected:
                    break

                try:
                    if isinstance(message, bytes):
                        # Raw audio binary frame
                        self._response_queue.put_nowait(message)
                    elif isinstance(message, str):
                        data = json.loads(message)
                        if "audio" in data:
                            audio_bytes = base64.b64decode(data["audio"])
                            self._response_queue.put_nowait(audio_bytes)
                        elif "error" in data:
                            logger.error("Smallest TTS provider error")
                            self._consecutive_errors += 1
                            if self._consecutive_errors >= 3:
                                raise TTSConnectionClosed(
                                    f"Smallest TTS: {self._consecutive_errors} errors"
                                )
                except asyncio.QueueFull:
                    logger.warning("Smallest TTS response queue full, dropping chunk")
                except json.JSONDecodeError:
                    continue

        except websockets.exceptions.ConnectionClosed:
            logger.info("Smallest TTS WebSocket closed")
        except TTSConnectionClosed:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Smallest TTS receive loop failed error_type=%s",
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

        logger.info("Smallest TTS adapter disconnected")

    async def send_text(self, text: str) -> None:
        """Send text for synthesis via WebSocket."""
        if not self._connected or not self._ws:
            raise TTSConnectionFailed("Not connected. Call connect() first.")
        if not text or not text.strip():
            return

        try:
            message = json.dumps(
                {
                    "text": text,
                    "voice_id": self._config.voice_id,
                    "language": self._config.language,
                    "sample_rate": self._config.sample_rate,
                    "add_wav_header": self._config.add_wav_header,
                }
            )
            await self._ws.send(message)
            self._consecutive_errors = 0
        except Exception as error:
            logger.error(
                "Smallest TTS send failed error_type=%s",
                type(error).__name__,
            )
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                raise TTSConnectionClosed(
                    f"Smallest TTS: {self._consecutive_errors} send failures"
                )

    async def receive_audio(self) -> Optional[bytes]:
        """Get next audio chunk from the response queue."""
        try:
            chunk = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def flush(self) -> None:
        """No explicit flush protocol for Smallest."""
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
        return "smallest"

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
