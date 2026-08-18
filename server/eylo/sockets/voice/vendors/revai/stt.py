"""Rev.AI Speech-to-Text implementation.

WebSocket-based real-time transcription with high accuracy.
Supports streaming audio in audio/x-raw format with partial and final transcripts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator, Literal

import numpy as np
import websockets
from websockets.asyncio.client import ClientConnection

from eylo.sockets.voice.audio import AudioFrame

logger = logging.getLogger(__name__)

REV_AI_WS_BASE = "wss://api.rev.ai/speechtotext/v1/stream"


def get_timestamp() -> float:
    """Get current timestamp in seconds."""
    return time.time()


@dataclass
class RevAIConfig:
    """Configuration for Rev.AI STT."""

    api_key: str
    """Rev.AI API access token."""

    sample_rate: int = 16000
    """Audio sample rate in Hz."""

    language: str = "en"
    """Language code (e.g., 'en', 'es')."""

    content_type: str = (
        "audio/x-raw;layout=interleaved;rate=16000;format=S16LE;channels=1"
    )
    """Audio content type specification."""


@dataclass
class TranscriptEvent:
    """Event emitted by Rev.AI STT stream."""

    type: Literal["PARTIAL", "FINAL", "ERROR", "CONNECTED"]
    """Type of transcript event."""

    text: str
    """Transcribed text content."""

    confidence: float
    """Confidence score (0.0 to 1.0)."""

    is_final: bool
    """Whether this is a final transcript."""

    timestamp: float = 0.0
    """Timestamp when event was created."""


class RevAISTTStream:
    """Stream for processing audio and receiving transcripts from Rev.AI."""

    def __init__(
        self,
        *,
        config: RevAIConfig,
    ) -> None:
        """Initialize Rev.AI STT stream.

        Args:
            config: Configuration for Rev.AI STT

        """
        self._config = config
        self._queue: asyncio.Queue[TranscriptEvent] = asyncio.Queue()
        self._closed = False
        self._ws: ClientConnection | None = None
        self._sender_task: asyncio.Task | None = None
        self._receiver_task: asyncio.Task | None = None
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._last_signal_time = get_timestamp()

    def _build_websocket_url(self) -> str:
        """Build Rev.AI WebSocket URL with parameters."""
        params = {
            "access_token": self._config.api_key,
            "content_type": self._config.content_type,
        }

        param_str = "&".join([f"{key}={value}" for key, value in params.items()])
        return f"{REV_AI_WS_BASE}?{param_str}"

    async def _sender_loop(self, ws: ClientConnection) -> None:
        """Send audio data to Rev.AI WebSocket."""
        try:
            while not self._closed:
                try:
                    data = await asyncio.wait_for(self._audio_queue.get(), timeout=5.0)
                    await ws.send(data)
                except asyncio.TimeoutError:
                    continue
                except Exception as error:
                    logger.error(
                        "Rev.AI audio send failed error_type=%s",
                        type(error).__name__,
                    )
                    break
        except Exception as error:
            logger.error(
                "Rev.AI sender loop failed error_type=%s",
                type(error).__name__,
            )
        finally:
            # Send close message
            try:
                if not self._closed and ws.open:
                    close_msg = json.dumps({"type": "CloseStream"})
                    await ws.send(close_msg)
            except Exception:
                pass
            logger.debug("Rev.AI sender loop terminated")

    async def _receiver_loop(self, ws: ClientConnection) -> None:
        """Receive transcripts from Rev.AI WebSocket."""
        buffer = ""

        try:
            while not self._closed:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)

                    # Handle connection confirmation
                    if data.get("type") == "connected":
                        logger.info("Rev.AI connection established")
                        await self._queue.put(
                            TranscriptEvent(
                                type="CONNECTED",
                                text="",
                                confidence=1.0,
                                is_final=False,
                                timestamp=get_timestamp(),
                            )
                        )
                        continue

                    # Extract text from elements
                    is_final = data.get("type") == "final"
                    elements = data.get("elements", [])
                    new_text = "".join([e.get("value", "") for e in elements])

                    # Update buffer
                    if len(new_text) > len(buffer):
                        self._last_signal_time = get_timestamp()

                    buffer = new_text

                    # Emit transcript event
                    if buffer:
                        confidence = (
                            1.0  # Rev.AI doesn't provide confidence in the same way
                        )
                        event = TranscriptEvent(
                            type="FINAL" if is_final else "PARTIAL",
                            text=buffer,
                            confidence=confidence,
                            is_final=is_final,
                            timestamp=get_timestamp(),
                        )
                        await self._queue.put(event)

                        # Clear buffer on final transcript
                        if is_final:
                            buffer = ""

                except websockets.exceptions.ConnectionClosedError:
                    logger.debug("Rev.AI connection closed")
                    break
                except json.JSONDecodeError:
                    logger.error("Error decoding Rev.AI response")
                    continue
                except Exception as error:
                    logger.error(
                        "Rev.AI receive failed error_type=%s",
                        type(error).__name__,
                    )
                    break
        except Exception as error:
            logger.error(
                "Rev.AI receiver loop failed error_type=%s",
                type(error).__name__,
            )
        finally:
            logger.debug("Rev.AI receiver loop terminated")

    async def start(self) -> None:
        """Start the WebSocket connection and processing tasks."""
        if self._ws:
            logger.warning("Stream already started")
            return

        try:
            url = self._build_websocket_url()
            self._ws = await websockets.connect(url)

            # Start sender and receiver tasks
            self._sender_task = asyncio.create_task(self._sender_loop(self._ws))
            self._receiver_task = asyncio.create_task(self._receiver_loop(self._ws))

            logger.info("Rev.AI STT stream started")

        except Exception as error:
            logger.error(
                "Rev.AI stream start failed error_type=%s",
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

        # Rev.AI expects raw PCM data (S16LE format)
        self._audio_queue.put_nowait(data)

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

        logger.info("Rev.AI STT stream closed")

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


class RevAISTT:
    """Rev.AI Speech-to-Text service."""

    def __init__(
        self,
        *,
        api_key: str,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> None:
        """Initialize Rev.AI STT.

        Args:
            api_key: Rev.AI API access token
            sample_rate: Audio sample rate in Hz (default: 16000)
            language: Language code (default: 'en')

        """
        # Build content type string
        content_type = (
            f"audio/x-raw;layout=interleaved;rate={sample_rate};format=S16LE;channels=1"
        )

        self._config = RevAIConfig(
            api_key=api_key,
            sample_rate=sample_rate,
            language=language,
            content_type=content_type,
        )

    @property
    def model(self) -> str:
        """Get model name."""
        return "rev-ai"

    @property
    def provider(self) -> str:
        """Get provider name."""
        return "Rev.AI"

    def stream(
        self,
        *,
        language: str | None = None,
        sample_rate: int | None = None,
    ) -> RevAISTTStream:
        """Create a new stream for transcription.

        Args:
            language: Override language code
            sample_rate: Override sample rate

        Returns:
            RevAISTTStream for processing audio

        """
        sr = sample_rate or self._config.sample_rate
        content_type = (
            f"audio/x-raw;layout=interleaved;rate={sr};format=S16LE;channels=1"
        )

        config = RevAIConfig(
            api_key=self._config.api_key,
            sample_rate=sr,
            language=language or self._config.language,
            content_type=content_type,
        )

        return RevAISTTStream(config=config)
