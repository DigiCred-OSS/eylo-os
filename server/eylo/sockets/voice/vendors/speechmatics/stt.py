"""Speechmatics STT - WebSocket streaming speech recognition.

Speechmatics provides enterprise-grade speech recognition with support for
50+ languages, speaker diarization, and custom vocabularies. This implementation
uses WebSocket streaming for real-time transcription.

Based on: livekit-plugins-speechmatics/livekit/plugins/speechmatics/stt.py
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from eylo.sockets.voice.audio import AudioFrame
from eylo.sockets.voice.types import NOT_GIVEN, NotGivenOr

# Speechmatics models
SpeechmaticsModels = Literal[
    "en",  # English model (optimized)
    "global",  # Global multilingual model
]

# Speechmatics languages (subset of most common - full list has 50+)
SpeechmaticsLanguages = Literal[
    "en",  # English (auto-detect dialect)
    "es",  # Spanish
    "fr",  # French
    "de",  # German
    "it",  # Italian
    "pt",  # Portuguese
    "nl",  # Dutch
    "pl",  # Polish
    "ru",  # Russian
    "ja",  # Japanese
    "zh",  # Chinese (Mandarin)
    "ko",  # Korean
    "ar",  # Arabic
    "hi",  # Hindi
    "tr",  # Turkish
    "sv",  # Swedish
    "no",  # Norwegian
    "da",  # Danish
    "fi",  # Finnish
    "cs",  # Czech
    "el",  # Greek
    "he",  # Hebrew
    "id",  # Indonesian
    "ms",  # Malay
    "th",  # Thai
    "vi",  # Vietnamese
    "uk",  # Ukrainian
    "ro",  # Romanian
    "hu",  # Hungarian
    "bg",  # Bulgarian
    "hr",  # Croatian
    "sk",  # Slovak
    "sl",  # Slovenian
    "et",  # Estonian
    "lv",  # Latvian
    "lt",  # Lithuanian
]

# Speechmatics WebSocket endpoints
DEFAULT_BASE_URL = "wss://eu2.rt.speechmatics.com/v2"
SAMPLE_RATE = 16000


@dataclass
class STTOptions:
    """Speechmatics STT configuration."""

    language: str
    enable_partials: bool
    enable_entities: bool
    max_delay: float
    sample_rate: int
    api_key: str
    endpoint_url: str
    diarization: str | None
    custom_vocabulary: list[str] | None


class SpeechmaticsSTT:
    """Speechmatics STT using real-time API via WebSocket streaming."""

    def __init__(
        self,
        *,
        language: SpeechmaticsLanguages | str = "en",
        enable_partials: bool = True,
        enable_entities: bool = False,
        max_delay: float = 2.0,
        sample_rate: int = SAMPLE_RATE,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: str = DEFAULT_BASE_URL,
        diarization: Literal["speaker"] | None = None,
        custom_vocabulary: list[str] | None = None,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if api_key is NOT_GIVEN or not api_key:
            raise ValueError("Speechmatics api_key is required.")

        self._session = http_session
        self._opts = STTOptions(
            language=language,
            enable_partials=enable_partials,
            enable_entities=enable_entities,
            max_delay=max_delay,
            sample_rate=sample_rate,
            api_key=api_key,
            endpoint_url=base_url,
            diarization=diarization,
            custom_vocabulary=custom_vocabulary,
        )

    @property
    def language(self) -> str:
        """Get the language being used."""
        return self._opts.language

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "Speechmatics"

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._opts.sample_rate

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    def stream(self) -> SpeechmaticsSTTStream:
        """Create a streaming STT session."""
        return SpeechmaticsSTTStream(
            opts=self._opts,
            http_session=self._ensure_session(),
        )

    async def aclose(self) -> None:
        """Close HTTP session if owned by this instance."""
        if self._session:
            await self._session.close()
            self._session = None


class SpeechmaticsSTTStream:
    """Speechmatics WebSocket streaming STT session.

    Manages WebSocket connection to Speechmatics for real-time transcription.
    Automatically handles reconnection, keepalive messages, and audio chunking.

    Protocol:
        1. Send StartRecognition message with configuration
        2. Send AddAudio messages with binary audio data
        3. Receive AddTranscript messages with results
        4. Send EndOfStream when done
        5. Receive EndOfTranscript as final confirmation

    Message Types:
        - AddPartialTranscript: Interim results (if enable_partials=True)
        - AddTranscript: Final transcription results
        - RecognitionStarted: Connection established
        - AudioAdded: Audio chunk received
        - EndOfTranscript: All transcription complete
        - Error: Transcription errors
    """

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
        self._recognized_started = False

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
        """Connect to Speechmatics WebSocket."""
        headers = {
            "Authorization": f"Bearer {self._opts.api_key}",
        }

        ws = await self._session.ws_connect(
            self._opts.endpoint_url,
            headers=headers,
            autoping=True,
            heartbeat=30,
        )

        return ws

    def _build_config_message(self) -> dict[str, Any]:
        """Build StartRecognition configuration message."""
        config: dict[str, Any] = {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._opts.sample_rate,
            },
            "transcription_config": {
                "language": self._opts.language,
                "enable_partials": self._opts.enable_partials,
                "enable_entities": self._opts.enable_entities,
                "max_delay": self._opts.max_delay,
            },
        }

        # Add optional configurations
        if self._opts.diarization:
            config["transcription_config"]["diarization"] = self._opts.diarization

        if self._opts.custom_vocabulary:
            config["transcription_config"]["additional_vocab"] = [
                {"content": word} for word in self._opts.custom_vocabulary
            ]

        return config

    async def _run(self) -> None:
        """Main WebSocket task loop."""
        try:
            while not self._closed:
                try:
                    await self._run_ws()
                except Exception:
                    if self._closed:
                        break
                    # Log error and reconnect
                    await asyncio.sleep(1)
                    self._reconnect_event.set()
        finally:
            await self._output_queue.put(None)

    async def _run_ws(self) -> None:
        """Run WebSocket connection."""
        self._ws = await self._connect_ws()

        # Send initial configuration
        config_msg = self._build_config_message()
        await self._ws.send_str(json.dumps(config_msg))

        # Start tasks
        send_task = asyncio.create_task(self._send_task())
        recv_task = asyncio.create_task(self._recv_task())

        try:
            await asyncio.gather(send_task, recv_task)
        finally:
            send_task.cancel()
            recv_task.cancel()

            try:
                await asyncio.gather(send_task, recv_task, return_exceptions=True)
            except Exception:
                pass

            if self._ws:
                await self._ws.close()
                self._ws = None

    async def _send_task(self) -> None:
        """Send audio data to WebSocket."""
        while not self._closed:
            frame = await self._input_queue.get()

            if frame is None:
                # Flush signal - send EndOfStream
                if self._ws:
                    await self._ws.send_str(json.dumps({"message": "EndOfStream"}))
                continue

            if self._ws and self._recognized_started:
                # Send audio as binary data
                # Speechmatics expects raw PCM data
                # frame.data is already bytes for Speechmatics
                await self._ws.send_bytes(frame.data)

    async def _recv_task(self) -> None:
        """Receive transcription results from WebSocket."""
        if not self._ws:
            return

        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                message_type = data.get("message")

                if message_type == "RecognitionStarted":
                    self._recognized_started = True
                    continue

                elif message_type in ("AddPartialTranscript", "AddTranscript"):
                    # Forward transcription events to output queue
                    await self._output_queue.put(data)

                elif message_type == "EndOfTranscript":
                    # Transcription complete
                    break

                elif message_type == "AudioAdded":
                    # Audio chunk acknowledged (can be ignored)
                    continue

                elif message_type == "Error":
                    # Error occurred
                    error_msg = data.get("reason", "Unknown error")
                    raise RuntimeError(f"Speechmatics error: {error_msg}")

            elif msg.type == aiohttp.WSMsgType.ERROR:
                raise RuntimeError(f"WebSocket error: {msg.data}")

    async def aclose(self) -> None:
        """Close the stream."""
        if self._closed:
            return

        self._closed = True
        await self._input_queue.put(None)  # Wake up send task

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()

        if self._ws:
            await self._ws.close()
            self._ws = None
