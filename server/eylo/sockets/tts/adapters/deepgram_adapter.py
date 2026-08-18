"""Deepgram TTS adapter for the production TTS manager.

Bridges Deepgram's Aura TTS WebSocket streaming API to the interface
expected by TTSRealtime/TTSFactory.

Deepgram TTS supports native WebSocket streaming, making this a natural
fit for the streaming pipeline without the HTTP→chunking workaround.
"""

import asyncio
import json
import logging
from typing import Optional

import aiohttp

from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.exceptions import TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

_DEFAULT_SAMPLE_RATE = 24000
_WS_URL = "wss://api.deepgram.com/v1/speak"


class DeepgramTTSConfig:
    """Configuration for Deepgram TTS adapter."""

    def __init__(
        self,
        *,
        model: str,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        encoding: str = "linear16",
        container: str = "none",
        api_key: str,
        ws_url: str = _WS_URL,
        **kwargs,  # Accept extra keys from tts_config without breaking
    ):
        self.model = model
        self.sample_rate = sample_rate
        self.encoding = {
            "pcm_s16le": "linear16",
            "pcm_mulaw": "mulaw",
            "pcm_alaw": "alaw",
        }.get(encoding, encoding)
        self.container = container
        self.api_key = api_key
        self.ws_url = ws_url

        if not self.api_key:
            raise ValueError("Deepgram TTS api_key is required.")


class DeepgramTTSAdapter(TTSVendorAdapter):
    """Adapter bridging Deepgram WebSocket TTS to the TTSFactory interface.

    Maintains a persistent WebSocket connection to Deepgram's TTS endpoint
    and translates between the Eylo streaming interface and Deepgram's
    Speak/Flush protocol.
    """

    def __init__(self, config: DeepgramTTSConfig):
        if config.container not in {"none", "raw"}:
            raise ValueError("Deepgram TTS must emit raw audio for realtime voice.")
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
            "encoding": getattr(config, "encoding", None),
        }
        super().__init__(
            TTSConfig(
                vendor="deepgram",
                **{k: v for k, v in _contract.items() if v is not None},
            )
        )
        self._config = config
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._recv_task: Optional[asyncio.Task] = None

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with query parameters."""
        params = {
            "model": self._config.model,
            "encoding": self._config.encoding,
            "container": self._config.container,
            "sample_rate": self._config.sample_rate,
        }
        url = self._config.ws_url
        separator = "&" if "?" in url else "?"
        return url + separator + "&".join(f"{k}={v}" for k, v in params.items())

    async def connect(self):
        """Connect to Deepgram TTS WebSocket."""
        self._session = aiohttp.ClientSession()

        try:
            url = self._build_ws_url()
            self._ws = await asyncio.wait_for(
                self._session.ws_connect(
                    url,
                    headers={"Authorization": f"Token {self._config.api_key}"},
                ),
                timeout=10.0,
            )
            self._connected = True
            # Start background receive loop
            self._recv_task = asyncio.create_task(self._receive_loop())
            logger.info("Deepgram TTS adapter connected (model=%s)", self._config.model)
            return self
        except Exception as error:
            if self._session:
                await self._session.close()
                self._session = None
            raise TTSConnectionFailed("Failed to connect Deepgram TTS.") from error

    async def _receive_loop(self):
        """Background loop reading audio frames from Deepgram WebSocket."""
        try:
            while self._connected and self._ws and not self._ws.closed:
                msg = await self._ws.receive()

                if msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                ):
                    logger.info("Deepgram TTS WebSocket closed")
                    break

                if msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        self._response_queue.put_nowait(msg.data)
                    except asyncio.QueueFull:
                        logger.warning(
                            "Deepgram TTS response queue full, dropping chunk"
                        )
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    # Control messages (Flushed, Warning, etc.)
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get("type", "")
                        if msg_type == "Flushed":
                            logger.debug("Deepgram TTS: Flushed signal received")
                        elif msg_type == "Warning":
                            logger.warning("Deepgram TTS provider warning")
                    except json.JSONDecodeError:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Deepgram TTS receive loop failed error_type=%s",
                type(error).__name__,
            )

    async def disconnect(self):
        """Close WebSocket and HTTP session."""
        self._connected = False

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ws and not self._ws.closed:
            # Send close message per Deepgram protocol
            try:
                await self._ws.send_str(json.dumps({"type": "Close"}))
            except Exception:
                pass
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("Deepgram TTS adapter disconnected")

    async def send_text(self, text: str) -> None:
        """Send text for synthesis via WebSocket.

        Args:
            text: Text to synthesize.

        """
        if not self._connected or not self._ws or self._ws.closed:
            raise TTSConnectionFailed("Not connected. Call connect() first.")
        if not text or not text.strip():
            return

        await self._ws.send_str(json.dumps({"type": "Speak", "text": text}))

    async def receive_audio(self) -> Optional[bytes]:
        """Get next audio chunk from the response queue.

        Returns:
            Audio bytes (linear16 PCM) or None if queue empty.

        """
        try:
            chunk = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def flush(self) -> None:
        """Send Flush signal to Deepgram to finalize current synthesis."""
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send_str(json.dumps({"type": "Flush"}))
            except Exception as error:
                logger.error(
                    "Deepgram TTS flush failed error_type=%s",
                    type(error).__name__,
                )

    async def handle_interruption(self):
        """Handle user interruption — flush synthesis and clear queue."""
        # Send flush to stop current synthesis
        await self.flush()

        # Drain response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def keepalive(self):
        """Send keepalive to maintain WebSocket connection.

        Deepgram WebSocket connections can timeout after inactivity.
        Sending a Flush on an empty buffer acts as a no-op keepalive.
        """
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send_str(json.dumps({"type": "Flush"}))
            except Exception:
                pass

    @property
    def sample_rate(self) -> int:
        """Audio sample rate."""
        return self._config.sample_rate

    @property
    def provider(self) -> str:
        return "deepgram"

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
            speed_control=False,
            voice_cloning=False,
            context_continuity=False,
        )
