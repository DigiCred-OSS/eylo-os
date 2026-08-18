"""Deepgram STT - WebSocket streaming speech recognition.

Deepgram provides industry-leading speech recognition with Nova-2 and Nova-3
models. This implementation uses WebSocket streaming for real-time transcription.

Based on: livekit-plugins-deepgram/livekit/plugins/deepgram/stt.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Literal

import aiohttp

from eylo.sockets.voice.audio import AudioByteStream, AudioFrame
from eylo.sockets.voice.types import NOT_GIVEN, NotGivenOr

logger = logging.getLogger(__name__)

# Deepgram models
DeepgramModels = Literal[
    "nova-2",
    "nova-2-general",
    "nova-2-meeting",
    "nova-2-phonecall",
    "nova-2-voicemail",
    "nova-2-finance",
    "nova-2-conversationalai",
    "nova-2-video",
    "nova-2-medical",
    "nova-2-drivethru",
    "nova-2-automotive",
    "nova-3",
    "nova-3-general",
    "nova-3-medical",
]

# Deepgram languages (subset of most common)
DeepgramLanguages = Literal[
    "en",
    "en-US",
    "en-GB",
    "en-AU",
    "en-NZ",
    "en-IN",
    "es",
    "es-419",
    "fr",
    "fr-CA",
    "de",
    "pt",
    "pt-BR",
    "zh",
    "zh-CN",
    "zh-TW",
    "ja",
    "ko",
    "hi",
    "it",
    "nl",
    "ru",
    "sv",
    "pl",
    "tr",
    "uk",
    "id",
    "ms",
    "th",
    "vi",
]

DEFAULT_BASE_URL = "wss://api.deepgram.com/v1/listen"
SAMPLE_RATE = 16000


@dataclass
class STTOptions:
    """Deepgram STT configuration."""

    model: str
    language: str
    interim_results: bool
    punctuate: bool
    smart_format: bool
    sample_rate: int
    api_key: str
    endpoint_url: str


class DeepgramSTT:
    """Deepgram STT using Nova models via WebSocket streaming."""

    def __init__(
        self,
        *,
        model: DeepgramModels | str = "nova-2",
        language: DeepgramLanguages | str = "en-US",
        interim_results: bool = True,
        punctuate: bool = True,
        smart_format: bool = False,
        sample_rate: int = SAMPLE_RATE,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: str = DEFAULT_BASE_URL,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if api_key is NOT_GIVEN or not api_key:
            raise ValueError("Deepgram api_key is required.")

        self._session = http_session
        self._opts = STTOptions(
            model=model,
            language=language,
            interim_results=interim_results,
            punctuate=punctuate,
            smart_format=smart_format,
            sample_rate=sample_rate,
            api_key=api_key,
            endpoint_url=base_url,
        )

    @property
    def model(self) -> str:
        """Get the STT model being used."""
        return self._opts.model

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "Deepgram"

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._opts.sample_rate

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    def stream(self) -> DeepgramSTTStream:
        """Create a streaming STT session."""
        return DeepgramSTTStream(
            opts=self._opts,
            http_session=self._ensure_session(),
        )

    async def aclose(self) -> None:
        """Close HTTP session if owned by this instance."""
        if self._session:
            await self._session.close()
            self._session = None


class DeepgramSTTStream:
    """Deepgram WebSocket streaming STT session.

    Manages WebSocket connection to Deepgram for real-time transcription.
    Automatically handles reconnection, keepalive messages, and audio chunking.
    """

    _KEEPALIVE_MSG = json.dumps({"type": "KeepAlive"})
    _CLOSE_MSG = json.dumps({"type": "CloseStream"})

    def __init__(
        self,
        *,
        opts: STTOptions,
        http_session: aiohttp.ClientSession,
    ) -> None:
        self._opts = opts
        self._session = http_session
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reconnect_event = asyncio.Event()
        self._closed = False

        # Audio input queue
        self._input_queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue()

        # Transcription output queue
        self._output_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        # Start background task
        self._task = asyncio.create_task(self._run())

    async def push_audio(self, frame: AudioFrame) -> None:
        """Push audio frame for transcription.

        Args:
            frame: AudioFrame to transcribe.

        """
        if not self._closed:
            await self._input_queue.put(frame)

    async def flush(self) -> None:
        """Flush any pending audio and get final transcription."""
        if not self._closed:
            await self._input_queue.put(None)  # Sentinel for flush

    def __aiter__(self):
        """Async iterator for transcription events."""
        return self

    async def __anext__(self) -> dict:
        """Get next transcription event.

        Returns:
            dict with transcription data.

        Raises:
            StopAsyncIteration when stream is closed.

        """
        event = await self._output_queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def _connect_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Connect to Deepgram WebSocket."""
        # Build WebSocket URL with parameters
        params = {
            "model": self._opts.model,
            "language": self._opts.language,
            "punctuate": str(self._opts.punctuate).lower(),
            "smart_format": str(self._opts.smart_format).lower(),
            "interim_results": str(self._opts.interim_results).lower(),
            "encoding": "linear16",
            "sample_rate": self._opts.sample_rate,
            "channels": 1,
            "vad_events": "true",
        }

        # Build URL
        url = self._opts.endpoint_url
        if "?" in url:
            url += "&"
        else:
            url += "?"
        url += "&".join(f"{k}={v}" for k, v in params.items())

        # Connect
        try:
            ws = await asyncio.wait_for(
                self._session.ws_connect(
                    url,
                    headers={"Authorization": f"Token {self._opts.api_key}"},
                ),
                timeout=10.0,
            )
            return ws
        except Exception as error:
            raise RuntimeError("Failed to connect to Deepgram.") from error

    async def _run(self) -> None:
        """Main streaming loop with reconnection logic."""

        async def keepalive_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Send periodic keepalive messages."""
            try:
                if "flux" in self._opts.model.lower():
                    logger.info("Flux: Skipping keepalive task")
                    return

                while True:
                    await ws.send_str(self._KEEPALIVE_MSG)
                    await asyncio.sleep(5)
            except Exception:
                return

        async def send_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Send audio to Deepgram."""
            # Audio chunking - 50ms chunks for optimal performance
            audio_bstream = AudioByteStream(
                sample_rate=self._opts.sample_rate,
                num_channels=1,
                samples_per_channel=self._opts.sample_rate // 20,  # 50ms
            )

            while True:
                frame = await self._input_queue.get()

                if frame is None:  # Flush sentinel
                    # Get remaining chunks
                    chunks = audio_bstream.flush()
                    for chunk in chunks:
                        await ws.send_bytes(chunk.data)
                    continue

                # Buffer frame and get 50ms chunks
                chunks = audio_bstream.write(frame.data)
                for chunk in chunks:
                    await ws.send_bytes(chunk.data)

        async def recv_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Receive transcriptions from Deepgram."""
            while True:
                msg = await ws.receive()

                if msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    if self._closed:
                        return
                    raise RuntimeError("Deepgram connection closed unexpectedly")

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._output_queue.put(data)

        # Main reconnection loop
        while not self._closed:
            try:
                ws = await self._connect_ws()
                self._ws = ws

                # Start tasks
                tasks = [
                    asyncio.create_task(keepalive_task(ws)),
                    asyncio.create_task(send_task(ws)),
                    asyncio.create_task(recv_task(ws)),
                ]

                wait_reconnect_task = asyncio.create_task(self._reconnect_event.wait())

                try:
                    done, _ = await asyncio.wait(
                        tasks + [wait_reconnect_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Check for exceptions
                    for task in done:
                        if task != wait_reconnect_task and not task.cancelled():
                            task.result()  # Raise exception if any

                    if wait_reconnect_task not in done:
                        break  # Normal termination

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
                # Wait before reconnecting
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
            await self._ws.send_str(self._CLOSE_MSG)
            await self._ws.close()
