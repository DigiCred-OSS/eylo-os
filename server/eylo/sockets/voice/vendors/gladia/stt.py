"""Gladia Speech-to-Text implementation.

WebSocket-based real-time transcription with confidence scores.
Supports partial and final transcripts with high accuracy.
"""

from __future__ import annotations

import asyncio
import audioop
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Literal

import numpy as np
import websockets
from websockets.asyncio.client import ClientConnection

from eylo.sockets.voice.audio import AudioFrame

logger = logging.getLogger(__name__)

GLADIA_WS_URL = "wss://api.gladia.io/audio/text/audio-transcription"


@dataclass
class GladiaConfig:
    """Configuration for Gladia STT."""

    api_key: str
    """Gladia API key."""

    language: str = "en"
    """Language code (e.g., 'en', 'es', 'fr')."""

    sample_rate: int = 16000
    """Audio sample rate in Hz."""

    encoding: Literal["wav", "pcm"] = "wav"
    """Audio encoding format."""

    buffer_size_seconds: float = 0.1
    """Buffer size for audio chunks (seconds)."""


@dataclass
class TranscriptEvent:
    """Event emitted by Gladia STT stream."""

    type: Literal["PARTIAL", "FINAL", "ERROR"]
    """Type of transcript event."""

    text: str
    """Transcribed text content."""

    confidence: float
    """Confidence score (0.0 to 1.0)."""

    is_final: bool
    """Whether this is a final transcript."""

    language: str = ""
    """Detected language code."""


class GladiaSTTStream:
    """Stream for processing audio and receiving transcripts from Gladia."""

    def __init__(
        self,
        *,
        config: GladiaConfig,
    ) -> None:
        """Initialize Gladia STT stream.

        Args:
            config: Configuration for Gladia STT

        """
        self._config = config
        self._queue: asyncio.Queue[TranscriptEvent] = asyncio.Queue()
        self._closed = False
        self._ws: ClientConnection | None = None
        self._sender_task: asyncio.Task | None = None
        self._receiver_task: asyncio.Task | None = None
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._buffer = bytearray()

    async def _sender_loop(self, ws: ClientConnection) -> None:
        """Send audio data to Gladia WebSocket."""
        try:
            while not self._closed:
                try:
                    data = await asyncio.wait_for(self._audio_queue.get(), timeout=5.0)
                    await ws.send(
                        json.dumps(
                            {
                                "x_gladia_key": self._config.api_key,
                                "frames": self._encode_audio(data),
                            }
                        )
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception as error:
                    logger.error(
                        "Gladia audio send failed error_type=%s",
                        type(error).__name__,
                    )
                    break
        except Exception as error:
            logger.error(
                "Gladia sender loop failed error_type=%s",
                type(error).__name__,
            )
        finally:
            logger.debug("Gladia sender loop terminated")

    async def _receiver_loop(self, ws: ClientConnection) -> None:
        """Receive transcripts from Gladia WebSocket."""
        try:
            while not self._closed:
                try:
                    result_str = await ws.recv()
                    data = json.loads(result_str)

                    if "error" in data and data["error"]:
                        error_msg = str(data["error"])
                        logger.error("Gladia STT provider error")
                        await self._queue.put(
                            TranscriptEvent(
                                type="ERROR",
                                text=error_msg,
                                confidence=0.0,
                                is_final=False,
                            )
                        )
                        continue

                    if data:
                        is_final = data.get("type") == "final"
                        transcription = data.get("transcription", "")
                        confidence = data.get("confidence", 1.0)
                        language = data.get("language", "")

                        if transcription:
                            event = TranscriptEvent(
                                type="FINAL" if is_final else "PARTIAL",
                                text=transcription,
                                confidence=confidence,
                                is_final=is_final,
                                language=language,
                            )
                            await self._queue.put(event)

                except websockets.exceptions.ConnectionClosedError:
                    logger.debug("Gladia connection closed")
                    break
                except Exception as error:
                    logger.error(
                        "Gladia receive failed error_type=%s",
                        type(error).__name__,
                    )
                    break
        except Exception as error:
            logger.error(
                "Gladia receiver loop failed error_type=%s",
                type(error).__name__,
            )
        finally:
            logger.debug("Gladia receiver loop terminated")

    def _encode_audio(self, data: bytes) -> str:
        """Encode audio data as base64 for Gladia API."""
        import base64

        return base64.b64encode(data).decode("utf-8")

    async def start(self) -> None:
        """Start the WebSocket connection and processing tasks."""
        if self._ws:
            logger.warning("Stream already started")
            return

        try:
            self._ws = await websockets.connect(GLADIA_WS_URL)

            # Send initial configuration
            await self._ws.send(
                json.dumps(
                    {
                        "x_gladia_key": self._config.api_key,
                        "sample_rate": self._config.sample_rate,
                        "encoding": self._config.encoding,
                    }
                )
            )

            # Start sender and receiver tasks
            self._sender_task = asyncio.create_task(self._sender_loop(self._ws))
            self._receiver_task = asyncio.create_task(self._receiver_loop(self._ws))

            logger.info("Gladia STT stream started")

        except Exception as error:
            logger.error(
                "Gladia stream start failed error_type=%s",
                type(error).__name__,
            )
            raise

    def push_frame(self, frame: AudioFrame) -> None:
        """Push an audio frame for transcription.

        Args:
            frame: AudioFrame to process

        """
        if self._closed:
            raise RuntimeError("Stream is closed")

        # Convert frame data to bytes
        if isinstance(frame.data, np.ndarray):
            data = frame.data.tobytes()
        else:
            data = bytes(frame.data)

        # Handle MULAW encoding if needed
        if hasattr(frame, "format") and frame.format == "mulaw":
            data = audioop.ulaw2lin(data, 1)

        self._buffer.extend(data)

        # Send when buffer reaches threshold
        buffer_threshold = int(
            self._config.buffer_size_seconds * self._config.sample_rate * 2
        )
        if len(self._buffer) >= buffer_threshold:
            self._audio_queue.put_nowait(bytes(self._buffer))
            self._buffer.clear()

    async def aclose(self) -> None:
        """Close the stream and cleanup resources."""
        if self._closed:
            return

        self._closed = True

        # Cancel tasks
        if self._sender_task and not self._sender_task.done():
            self._sender_task.cancel()
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()

        # Wait for tasks to complete
        tasks = []
        if self._sender_task:
            tasks.append(self._sender_task)
        if self._receiver_task:
            tasks.append(self._receiver_task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Close WebSocket
        if self._ws:
            await self._ws.close()

        logger.info("Gladia STT stream closed")

    def __aiter__(self) -> AsyncIterator[TranscriptEvent]:
        """Make the stream async iterable."""
        return self

    async def __anext__(self) -> TranscriptEvent:
        """Get next transcript event."""
        if self._closed and self._queue.empty():
            raise StopAsyncIteration

        try:
            event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            return event
        except asyncio.TimeoutError:
            if self._closed:
                raise StopAsyncIteration
            # Continue waiting
            return await self.__anext__()


class GladiaSTT:
    """Gladia Speech-to-Text service."""

    def __init__(
        self,
        *,
        api_key: str,
        language: str = "en",
        sample_rate: int = 16000,
        encoding: Literal["wav", "pcm"] = "wav",
        buffer_size_seconds: float = 0.1,
    ) -> None:
        """Initialize Gladia STT.

        Args:
            api_key: Gladia API key
            language: Language code (default: 'en')
            sample_rate: Audio sample rate in Hz (default: 16000)
            encoding: Audio encoding format (default: 'wav')
            buffer_size_seconds: Buffer size for audio chunks (default: 0.1)

        """
        self._config = GladiaConfig(
            api_key=api_key,
            language=language,
            sample_rate=sample_rate,
            encoding=encoding,
            buffer_size_seconds=buffer_size_seconds,
        )

    @property
    def model(self) -> str:
        """Get model name."""
        return "gladia"

    @property
    def provider(self) -> str:
        """Get provider name."""
        return "Gladia"

    def stream(
        self,
        *,
        language: str | None = None,
        sample_rate: int | None = None,
    ) -> GladiaSTTStream:
        """Create a new stream for transcription.

        Args:
            language: Override language code
            sample_rate: Override sample rate

        Returns:
            GladiaSTTStream for processing audio

        """
        config = GladiaConfig(
            api_key=self._config.api_key,
            language=language or self._config.language,
            sample_rate=sample_rate or self._config.sample_rate,
            encoding=self._config.encoding,
            buffer_size_seconds=self._config.buffer_size_seconds,
        )

        return GladiaSTTStream(config=config)
