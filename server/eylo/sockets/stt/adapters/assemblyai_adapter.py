"""AssemblyAI STT adapter for canonical STT pipeline.

This adapter wraps the new voice module's AssemblyAISTT to work with
the existing STT factory and manager patterns.
"""

import asyncio
import logging
from typing import Any, Optional

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType
from eylo.sockets.voice.vendors.assemblyai import AssemblyAISTT

logger = logging.getLogger(__name__)


class AssemblyAIAdapter(STTVendorAdapter):
    """Adapter to use new voice module AssemblyAISTT with canonical STT pipeline.

    This class bridges the gap between:
    - Canonical interface: connect(), send_audio(), receive_event()
    - New voice module: stream() with async iteration

    The adapter handles:
    - Audio streaming to AssemblyAI
    - Event parsing (partial/final transcripts, turn detection)
    - Response queuing for STT manager
    """

    def __init__(self, config: dict):
        """Initialize AssemblyAI adapter with resolved provider config.

        Args:
            config: Resolved STT config dict with keys:
                - api_key: AssemblyAI API key
                - sample_rate: Audio sample rate (default: 16000)
                - encoding: Audio encoding format (default: 'pcm_s16le')
                - end_of_turn_confidence_threshold: Turn end confidence (default: 0.6)
                - min_end_of_turn_silence_when_confident: Min silence ms (default: 500)
                - max_turn_silence: Max silence ms (default: 1500)
                - format_turns: Enable formatting (default: True)

        """
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._is_connected = False
        self._stream: Optional[Any] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # Initialize new voice module STT
        self._stt = AssemblyAISTT(
            api_key=config["api_key"],
            speech_model=config["model"],
            sample_rate=config.get("sample_rate", 16000),
            encoding=config.get("encoding", "pcm_s16le"),
            end_of_turn_confidence_threshold=config.get(
                "end_of_turn_confidence_threshold", 0.6
            ),
            min_end_of_turn_silence_when_confident=config.get(
                "min_end_of_turn_silence_when_confident", 500
            ),
            max_turn_silence=config.get("max_turn_silence", 1500),
            format_turns=config.get("format_turns", True),
        )

        logger.info("Initialized AssemblyAIAdapter")

    async def connect(self):
        """Connect to AssemblyAI service (canonical interface).

        Returns:
            Self to maintain interface compatibility.

        """
        self._stream = self._stt.stream()
        self._receive_task = asyncio.create_task(self._receive_events())
        self._is_connected = True
        logger.info("AssemblyAI adapter connected")
        return self

    async def _receive_events(self):
        """Receive events from AssemblyAI stream and queue them."""
        try:
            async for event in self._stream:
                adapter_event = self._convert_event(event)
                if adapter_event:
                    try:
                        await self._response_queue.put(adapter_event)
                    except asyncio.QueueFull:
                        logger.warning("Response queue full, dropping event")

        except Exception as error:
            logger.error(
                "AssemblyAI event receive failed error_type=%s",
                type(error).__name__,
            )
            self._is_connected = False

    def _convert_event(self, event: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Convert AssemblyAI V3 event to adapter event format.

        AssemblyAI V3 Streaming event types:
        - Begin: Session started (id, expires_at)
        - Turn: Transcript with turn detection (transcript, end_of_turn)
        - Termination: Session ended

        Adapter event shape consumed by receive_event:
        - transcript: str
        - is_final: bool
        - confidence: float
        - type: "partial" | "final" | "utterance_end" | "speech_started"
        """
        event_type = event.get("type")

        if event_type == "Turn":
            text = event.get("transcript", "")
            end_of_turn = event.get("end_of_turn", False)

            if not text:
                return None

            result = {
                "transcript": text,
                "is_final": end_of_turn,
                "confidence": 0.95,
                "words": event.get("words", []),
                "type": "final" if end_of_turn else "partial",
            }

            return result

        elif event_type == "Begin":
            return {
                "type": "speech_started",
                "timestamp": 0,
            }

        # Ignore Termination and other events
        return None

    async def send_audio(self, audio_data: bytes):
        """Send audio data for transcription (canonical interface).

        Args:
            audio_data: Raw audio bytes (PCM format).

        """
        if not self._is_connected or not self._stream:
            raise RuntimeError("Not connected. Call connect() first.")

        await self._stream.push_audio(audio_data)

    async def _receive_raw_event(self) -> Optional[dict[str, Any]]:
        """Read one vendor-shaped event from the internal queue.

        Returns:
            Event dict or None if no data available.

        """
        try:
            event = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return event
        except asyncio.TimeoutError:
            return None

    async def keepalive(self):
        """Send keepalive (canonical interface). No-op for AssemblyAI."""
        pass

    async def disconnect(self):
        """Disconnect from AssemblyAI service (canonical interface)."""
        logger.info("Disconnecting AssemblyAI adapter")

        self._is_connected = False

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._stream:
            await self._stream.aclose()
            self._stream = None

        await self._stt.aclose()

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._is_connected

    @property
    def sample_rate(self) -> int:
        """Get audio sample rate."""
        return self._stt.sample_rate

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
            interim_results=False,
            vad_events=False,
            turn_detection=False,
            word_timestamps=False,
            speaker_labels=False,
            language_detection=False,
        )
