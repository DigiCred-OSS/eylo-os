"""Cartesia STT - ink-whisper speech recognition.

Cartesia provides ink-whisper model for real-time speech recognition
via WebSocket streaming.

Based on: livekit-plugins-cartesia/livekit/plugins/cartesia/stt.py
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Literal

import aiohttp

from eylo.sockets.voice.audio import AudioByteStream
from eylo.sockets.voice.types import NOT_GIVEN, NotGivenOr

# Cartesia STT models
CartesiaSTTModels = Literal["ink-whisper"]

# Cartesia STT languages
CartesiaSTTLanguages = Literal[
    "en", "es", "fr", "de", "pt", "zh", "ja", "ko", "it", "nl", "ru"
]

# Cartesia STT encoding
CartesiaSTTEncoding = Literal["pcm_s16le"]

DEFAULT_BASE_URL = "https://api.cartesia.ai"
API_VERSION = "2026-03-01"
SAMPLE_RATE = 16000


@dataclass
class STTOptions:
    """Cartesia STT configuration."""

    model: str
    language: str | None
    encoding: str
    sample_rate: int
    api_key: str
    base_url: str


class CartesiaSTT:
    """Cartesia STT using ink-whisper model."""

    def __init__(
        self,
        *,
        model: CartesiaSTTModels | str = "ink-whisper",
        language: CartesiaSTTLanguages | str = "en",
        encoding: CartesiaSTTEncoding = "pcm_s16le",
        sample_rate: int = SAMPLE_RATE,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: str = DEFAULT_BASE_URL,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if api_key is NOT_GIVEN or not api_key:
            raise ValueError("Cartesia api_key is required.")

        self._session = http_session
        self._opts = STTOptions(
            model=model,
            language=language,
            encoding=encoding,
            sample_rate=sample_rate,
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def model(self) -> str:
        """Get the STT model being used."""
        return self._opts.model

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "Cartesia"

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._opts.sample_rate

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    def stream(self) -> CartesiaSTTStream:
        """Create a streaming STT session.

        Returns:
            CartesiaSTTStream for real-time transcription.

        """
        return CartesiaSTTStream(
            opts=self._opts,
            http_session=self._ensure_session(),
        )

    async def aclose(self) -> None:
        """Close HTTP session if owned by this instance."""
        if self._session:
            await self._session.close()
            self._session = None


class CartesiaSTTStream:
    """Cartesia WebSocket streaming STT session."""

    def __init__(
        self,
        *,
        opts: STTOptions,
        http_session: aiohttp.ClientSession,
    ) -> None:
        self._opts = opts
        self._session = http_session
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._request_id = str(uuid.uuid4())
        self._reconnect_event = asyncio.Event()
        self._closed = False

        # Audio input queue
        self._input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        # Transcription output queue
        self._output_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        # Start background task
        self._task = asyncio.create_task(self._run())

    async def push_audio(self, audio_data: bytes) -> None:
        """Push audio data for transcription."""
        if not self._closed:
            await self._input_queue.put(audio_data)

    async def flush(self) -> None:
        """Flush any pending audio."""
        if not self._closed:
            await self._input_queue.put(None)  # Sentinel

    def __aiter__(self):
        """Async iterator for transcription events."""
        return self

    async def __anext__(self) -> dict:
        """Get next transcription event."""
        event = await self._output_queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def _connect_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Connect to Cartesia WebSocket."""
        # Build WebSocket URL
        params = {
            "model": self._opts.model,
            "sample_rate": str(self._opts.sample_rate),
            "encoding": self._opts.encoding,
            "cartesia_version": API_VERSION,
            "api_key": self._opts.api_key,
        }

        if self._opts.language:
            params["language"] = self._opts.language

        # Convert HTTP URL to WebSocket URL
        ws_base = self._opts.base_url.replace("https://", "wss://").replace(
            "http://", "ws://"
        )
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        ws_url = f"{ws_base}/stt/websocket?{query_string}"

        try:
            ws = await asyncio.wait_for(
                self._session.ws_connect(ws_url),
                timeout=10.0,
            )
            return ws
        except Exception as error:
            raise RuntimeError("Failed to connect to Cartesia.") from error

    async def _run(self) -> None:
        """Main streaming loop with reconnection logic."""

        async def keepalive_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Send periodic ping messages."""
            try:
                while True:
                    await ws.ping()
                    await asyncio.sleep(30)
            except Exception:
                return

        async def send_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Send audio to Cartesia."""
            # 50ms audio chunks
            samples_50ms = self._opts.sample_rate // 20
            audio_bstream = AudioByteStream(
                sample_rate=self._opts.sample_rate,
                num_channels=1,
                samples_per_channel=samples_50ms,
            )

            while True:
                data = await self._input_queue.get()

                if data is None:  # Flush sentinel
                    chunks = audio_bstream.flush()
                    for chunk in chunks:
                        await ws.send_bytes(chunk.data)
                    # Send finalize message
                    await ws.send_str("finalize")
                    return

                # Buffer data and get chunks
                chunks = audio_bstream.write(data)
                for chunk in chunks:
                    await ws.send_bytes(chunk.data)

        async def recv_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Receive transcriptions from Cartesia."""
            while True:
                msg = await ws.receive()

                if msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    if self._closed:
                        return
                    raise RuntimeError("Cartesia connection closed unexpectedly")

                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue

                try:
                    data = json.loads(msg.data)
                    await self._output_queue.put(data)
                except json.JSONDecodeError:
                    pass

        # Main reconnection loop
        while not self._closed:
            ws = None
            try:
                ws = await self._connect_ws()
                self._ws = ws

                # Start tasks
                tasks = [
                    asyncio.create_task(send_task(ws)),
                    asyncio.create_task(recv_task(ws)),
                    asyncio.create_task(keepalive_task(ws)),
                ]

                wait_reconnect_task = asyncio.create_task(self._reconnect_event.wait())

                try:
                    done, _ = await asyncio.wait(
                        [asyncio.gather(*tasks), wait_reconnect_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Check for exceptions
                    for task in done:
                        if task != wait_reconnect_task:
                            task.result()

                    if wait_reconnect_task not in done:
                        break

                    self._reconnect_event.clear()
                finally:
                    # Cancel all tasks
                    for task in tasks + [wait_reconnect_task]:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(
                        *tasks, wait_reconnect_task, return_exceptions=True
                    )
            except Exception:
                if self._closed:
                    break
                await asyncio.sleep(1)
            finally:
                if ws and not ws.closed:
                    await ws.close()

        # Signal end of stream
        await self._output_queue.put(None)

    async def aclose(self) -> None:
        """Close the stream and clean up resources."""
        self._closed = True
        self._reconnect_event.set()

        if self._task and not self._task.done():
            await self._task

        if self._ws and not self._ws.closed:
            await self._ws.close()
