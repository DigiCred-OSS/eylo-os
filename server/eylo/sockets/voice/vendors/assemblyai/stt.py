"""AssemblyAI STT - Real-time speech recognition with turn detection.

AssemblyAI provides industry-leading speech recognition with advanced
turn detection capabilities for natural conversation understanding.

Based on: livekit-plugins-assemblyai/livekit/plugins/assemblyai/stt.py
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp

from eylo.sockets.voice.audio import AudioByteStream
from eylo.sockets.voice.types import NOT_GIVEN, NotGivenOr

DEFAULT_API_URL = "wss://streaming.assemblyai.com/v3/ws"
SAMPLE_RATE = 16000


@dataclass
class STTOptions:
    """AssemblyAI STT configuration."""

    speech_model: str
    sample_rate: int
    encoding: str
    buffer_size_seconds: float
    end_of_turn_confidence_threshold: float
    min_end_of_turn_silence_when_confident: int
    max_turn_silence: int
    format_turns: bool
    keyterms_prompt: list[str] | None
    api_key: str


class AssemblyAISTT:
    """AssemblyAI STT with turn detection."""

    def __init__(
        self,
        *,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        speech_model: str = "universal",
        sample_rate: int = SAMPLE_RATE,
        encoding: str = "pcm_s16le",
        end_of_turn_confidence_threshold: float = 0.6,
        min_end_of_turn_silence_when_confident: int = 500,
        max_turn_silence: int = 1500,
        format_turns: bool = True,
        keyterms_prompt: list[str] | None = None,
        buffer_size_seconds: float = 0.05,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if api_key is NOT_GIVEN or not api_key:
            raise ValueError("AssemblyAI api_key is required.")

        self._session = http_session
        self._api_key = api_key
        self._opts = STTOptions(
            speech_model=speech_model,
            sample_rate=sample_rate,
            encoding=encoding,
            buffer_size_seconds=buffer_size_seconds,
            end_of_turn_confidence_threshold=end_of_turn_confidence_threshold,
            min_end_of_turn_silence_when_confident=min_end_of_turn_silence_when_confident,
            max_turn_silence=max_turn_silence,
            format_turns=format_turns,
            keyterms_prompt=keyterms_prompt,
            api_key=api_key,
        )

    @property
    def model(self) -> str:
        """Get the STT model being used."""
        return self._opts.speech_model

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "AssemblyAI"

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._opts.sample_rate

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    def stream(self) -> AssemblyAISTTStream:
        """Create a streaming STT session.

        Returns:
            AssemblyAISTTStream for real-time transcription with turn detection.

        """
        return AssemblyAISTTStream(
            opts=self._opts,
            api_key=self._api_key,
            http_session=self._ensure_session(),
        )

    def update_options(
        self,
        *,
        buffer_size_seconds: NotGivenOr[float] = NOT_GIVEN,
        end_of_turn_confidence_threshold: NotGivenOr[float] = NOT_GIVEN,
        min_end_of_turn_silence_when_confident: NotGivenOr[int] = NOT_GIVEN,
        max_turn_silence: NotGivenOr[int] = NOT_GIVEN,
    ) -> None:
        """Update STT options."""
        if buffer_size_seconds is not NOT_GIVEN:
            self._opts.buffer_size_seconds = buffer_size_seconds
        if end_of_turn_confidence_threshold is not NOT_GIVEN:
            self._opts.end_of_turn_confidence_threshold = (
                end_of_turn_confidence_threshold
            )
        if min_end_of_turn_silence_when_confident is not NOT_GIVEN:
            self._opts.min_end_of_turn_silence_when_confident = (
                min_end_of_turn_silence_when_confident
            )
        if max_turn_silence is not NOT_GIVEN:
            self._opts.max_turn_silence = max_turn_silence

    async def aclose(self) -> None:
        """Close HTTP session if owned by this instance."""
        if self._session:
            await self._session.close()
            self._session = None


class AssemblyAISTTStream:
    """AssemblyAI WebSocket streaming STT session with turn detection."""

    _CLOSE_MSG = json.dumps({"type": "Terminate"})

    def __init__(
        self,
        *,
        opts: STTOptions,
        api_key: str,
        http_session: aiohttp.ClientSession,
    ) -> None:
        self._opts = opts
        self._api_key = api_key
        self._session = http_session
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reconnect_event = asyncio.Event()
        self._closed = False

        # Audio input queue
        self._input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        # Transcription output queue
        self._output_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        # Start background task
        self._task = asyncio.create_task(self._run())

    async def push_audio(self, audio_data: bytes) -> None:
        """Push audio data for transcription.

        Args:
            audio_data: Raw audio bytes (PCM format).

        """
        if not self._closed:
            await self._input_queue.put(audio_data)

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
            dict with event data (SessionBegins, PartialTranscript, FinalTranscript, SessionTurn).

        Raises:
            StopAsyncIteration when stream is closed.

        """
        event = await self._output_queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def _connect_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Connect to AssemblyAI V3 WebSocket."""
        # Build configuration per V3 API spec
        live_config = {
            "speech_model": self._opts.speech_model,
            "sample_rate": self._opts.sample_rate,
            "encoding": self._opts.encoding,
            "end_of_turn_confidence_threshold": self._opts.end_of_turn_confidence_threshold,
            "min_turn_silence": self._opts.min_end_of_turn_silence_when_confident,
            "max_turn_silence": self._opts.max_turn_silence,
            "format_turns": "true" if self._opts.format_turns else "false",
            "keyterms_prompt": (
                ",".join(self._opts.keyterms_prompt)
                if self._opts.keyterms_prompt
                else None
            ),
        }

        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "AssemblyAI/1.0 (integration=Eylo)",
        }

        # Filter None values and convert bools to strings
        filtered_config = {
            k: ("true" if v else "false") if isinstance(v, bool) else v
            for k, v in live_config.items()
            if v is not None
        }

        url = f"{DEFAULT_API_URL}?{urlencode(filtered_config)}"

        try:
            ws = await self._session.ws_connect(url, headers=headers)
            return ws
        except Exception as error:
            raise RuntimeError("Failed to connect to AssemblyAI.") from error

    async def _run(self) -> None:
        """Main streaming loop with reconnection logic."""

        async def send_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Send audio to AssemblyAI."""
            # Calculate samples per buffer
            samples_per_buffer = self._opts.sample_rate // round(
                1 / self._opts.buffer_size_seconds
            )

            audio_bstream = AudioByteStream(
                sample_rate=self._opts.sample_rate,
                num_channels=1,
                samples_per_channel=samples_per_buffer,
            )

            while True:
                data = await self._input_queue.get()

                if data is None:  # Flush sentinel
                    chunks = audio_bstream.flush()
                    for chunk in chunks:
                        await ws.send_bytes(chunk.data)
                    continue

                # Buffer data and get chunks
                chunks = audio_bstream.write(data)
                for chunk in chunks:
                    await ws.send_bytes(chunk.data)

        async def recv_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            """Receive transcriptions from AssemblyAI."""
            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                except asyncio.TimeoutError:
                    if self._closed:
                        break
                    continue

                if msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    if self._closed:
                        return
                    raise RuntimeError("AssemblyAI connection closed unexpectedly")

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
                    await ws.send_str(self._CLOSE_MSG)
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
