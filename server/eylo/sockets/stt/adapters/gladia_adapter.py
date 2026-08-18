"""Gladia STT adapter for canonical STT pipeline.

This adapter wraps the new voice module's GladiaSTT to work with
the existing STT factory and manager patterns.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType
from eylo.sockets.voice.vendors.gladia import GladiaSTT, GladiaSTTStream

logger = logging.getLogger(__name__)


class GladiaAdapter(STTVendorAdapter):
    """Adapter to use new voice module GladiaSTT with canonical STT pipeline.

    This class bridges the gap between:
    - Canonical interface: connect(), send_audio(), receive_event()
    - New voice module: stream() with async iteration

    The adapter handles:
    - Audio streaming to Gladia
    - Event parsing (partial/final transcripts)
    - Response queuing for STT manager
    """

    def __init__(self, config: dict):
        """Initialize Gladia adapter with resolved provider config.

        Args:
            config: Resolved STT config dict with keys:
                - api_key: Gladia API key
                - language: Language code
                - sample_rate: Audio sample rate (default: 16000)
                - encoding: Audio encoding format (default: 'wav')
                - buffer_size_seconds: Buffer size (default: 0.1)

        """
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._is_connected = False
        self._stream: Optional[GladiaSTTStream] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # Initialize new voice module STT
        self._stt = GladiaSTT(
            api_key=config["api_key"],
            language=config["language"],
            sample_rate=config.get("sample_rate", 16000),
            encoding=config.get("encoding", "wav"),
            buffer_size_seconds=config.get("buffer_size_seconds", 0.1),
        )

        logger.info("Initialized GladiaAdapter with language=%s", config["language"])

    async def connect(self):
        """Connect to Gladia service (canonical interface).

        Returns:
            Self to maintain interface compatibility.

        """
        # Create stream
        self._stream = self._stt.stream()

        # Start WebSocket connection
        await self._stream.start()

        # Start background task to receive events
        self._receive_task = asyncio.create_task(self._receive_events())

        self._is_connected = True
        logger.info("Gladia adapter connected")
        return self

    async def _receive_events(self):
        """Receive events from Gladia stream and queue them.

        This background task continuously receives events from the voice module
        stream and puts them in the response queue for the STT manager.
        """
        try:
            async for event in self._stream:
                # Convert voice module event to adapter event format
                adapter_event = self._convert_event(event)
                if adapter_event:
                    try:
                        await self._response_queue.put(adapter_event)
                    except asyncio.QueueFull:
                        logger.warning("Response queue full, dropping event")

        except Exception as error:
            logger.error(
                "Gladia event receive failed error_type=%s",
                type(error).__name__,
            )
            self._is_connected = False

    def _convert_event(self, event) -> Optional[Dict[str, Any]]:
        """Convert voice module event format to adapter event format.

        Args:
            event: TranscriptEvent from voice module.

        Returns:
            Event in adapter event format or None if should be filtered.

        Gladia event types:
        - type: "PARTIAL" - interim results
        - type: "FINAL" - final results
        - type: "ERROR" - error occurred

        Adapter event shape consumed by receive_event:
        - transcript: str
        - is_final: bool
        - confidence: float
        - type: str

        """
        if event.type == "ERROR":
            logger.error("Gladia STT provider error")
            return {
                "type": "error",
                "error": event.text,
            }

        # Handle partial transcripts
        elif event.type == "PARTIAL":
            return {
                "transcript": event.text,
                "is_final": False,
                "confidence": event.confidence,
                "type": "partial",
                "language": event.language,
            }

        # Handle final transcripts
        elif event.type == "FINAL":
            return {
                "transcript": event.text,
                "is_final": True,
                "confidence": event.confidence,
                "type": "final",
                "language": event.language,
            }

        return None

    async def send_audio(self, audio_data: bytes):
        """Send audio data for transcription (canonical interface).

        Args:
            audio_data: Raw audio bytes (PCM format).

        """
        if not self._is_connected or not self._stream:
            raise RuntimeError("Not connected. Call connect() first.")

        # Push audio to stream
        from eylo.sockets.voice.audio import AudioFrame

        frame = AudioFrame(
            data=audio_data,
            sample_rate=self._stt._config.sample_rate,
            num_channels=1,
            samples_per_channel=len(audio_data) // 2,  # 16-bit PCM
        )

        self._stream.push_frame(frame)

    async def _receive_raw_event(self) -> Optional[Dict[str, Any]]:
        """Read one vendor-shaped event from the internal queue.

        Returns:
            Event dict or None if no data available.

        """
        try:
            # Non-blocking get with timeout
            event = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return event
        except asyncio.TimeoutError:
            return None

    async def keepalive(self):
        """Send keepalive (canonical interface).

        The new voice module handles keepalive internally, so this is a no-op.
        """
        pass

    async def disconnect(self):
        """Disconnect from Gladia service (canonical interface)."""
        logger.info("Disconnecting Gladia adapter")

        self._is_connected = False

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Close stream
        if self._stream:
            await self._stream.aclose()
            self._stream = None

        logger.info("Gladia adapter disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._is_connected

    @property
    def sample_rate(self) -> int:
        """Get audio sample rate."""
        return self._stt._config.sample_rate

    @property
    def provider(self) -> str:
        """Get provider name."""
        return self._stt.provider

    async def receive_event(self, timeout_ms: int = 100) -> STTEvent | None:
        """Next event as the canonical `STTEvent`.

        Adapts the queue `receive_event` already reads rather than replacing
        it, so the live path keeps its exact behaviour while the contract is
        young. Only fields the vendor actually reported are set — confidence and
        timings are left unset rather than invented.
        """
        raw = await self._receive_raw_event()
        if raw is None:
            return None
        event_type = raw.get("type") or raw.get("event")
        return STTEvent(
            type=STTEventType(event_type)
            if event_type in set(STTEventType)
            else STTEventType.TRANSCRIPT_PARTIAL,
            provider=self.provider,
            model=self.model,
            transcript=str(raw.get("transcript") or raw.get("text") or ""),
            is_final=bool(raw.get("is_final", False)),
            confidence=raw.get("confidence"),
            language=raw.get("language"),
        )

    async def flush(self) -> None:
        """No flush frame on this stream. Explicit, not faked."""
        return None

    @property
    def model(self) -> str:
        """From the vendor client — what actually connected."""
        return str(getattr(self._stt, "model", "") or "")

    @property
    def capabilities(self) -> STTCapabilities:
        """Derived from what this adapter's own code does, not from memory.

        Conservative where unknown: under-claiming makes a caller skip a
        feature, over-claiming makes it break. Confirm against vendor
        documentation before relying on a False here.
        """
        return STTCapabilities(
            streaming=True,
            batch_recognize=False,
            interim_results=True,
            vad_events=False,
            turn_detection=False,
            word_timestamps=False,
            speaker_labels=False,
            language_detection=False,
        )
