"""Deepgram STT adapter for canonical STT pipeline.

This adapter wraps the new voice module's DeepgramSTT to work with
the existing STT factory and manager patterns.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType
from eylo.sockets.voice.vendors.deepgram import DeepgramSTT, DeepgramSTTStream

logger = logging.getLogger(__name__)


class DeepgramAdapter(STTVendorAdapter):
    """Adapter to use new voice module DeepgramSTT with canonical STT pipeline.

    This class bridges the gap between:
    - Canonical interface: connect(), send_audio(), receive_event()
    - New voice module: stream() with async iteration

    The adapter handles:
    - Audio streaming to Deepgram
    - Event parsing (transcripts, VAD events)
    - Response queuing for STT manager
    """

    def __init__(self, config: dict):
        """Initialize Deepgram adapter with resolved provider config.

        Args:
            config: Resolved STT config dict with keys:
                - api_key: Deepgram API key
                - model: Model to use (e.g., "nova-2", "nova-3")
                - language: Language code
                - sample_rate: Audio sample rate
                - punctuate: Enable punctuation
                - interim_results: Enable interim results
                - vad_events: Enable VAD events
                - utterance_end_ms: Utterance end timeout
                - endpointing: Endpointing timeout

        """
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._is_connected = False
        self._stream: Optional[DeepgramSTTStream] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # Initialize new voice module STT
        self._stt = DeepgramSTT(
            model=config["model"],
            language=config["language"],
            sample_rate=config.get("sample_rate", 16000),
            interim_results=config.get("interim_results", True),
            punctuate=config.get("punctuate", True),
            api_key=config["api_key"],
        )

        logger.info(f"Initialized DeepgramAdapter with model={self._stt.model}")

    async def connect(self):
        """Connect to Deepgram service (canonical interface).

        Returns:
            Self to maintain interface compatibility.

        """
        # Create stream
        self._stream = self._stt.stream()

        # Start background task to receive events
        self._receive_task = asyncio.create_task(self._receive_events())

        self._is_connected = True
        logger.info("Deepgram adapter connected")
        return self

    async def _receive_events(self):
        """Receive events from Deepgram stream and queue them.

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
                "Deepgram event receive failed error_type=%s",
                type(error).__name__,
            )
            self._is_connected = False

    def _convert_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert voice module event format to adapter event format.

        Args:
            event: Event from voice module.

        Returns:
            Event in adapter event format or None if should be filtered.

        Voice module event types:
        - type: "Results" with channel/alternatives
        - type: "SpeechStarted"
        - type: "UtteranceEnd"
        - type: "Metadata"

        Adapter event shape consumed by receive_event:
        - transcript: str
        - is_final: bool
        - confidence: float
        - type: "speech_started" | "utterance_end" | etc.

        """
        event_type = event.get("type")

        # Handle transcript results
        if event_type in ("Results", "final_transcript", "partial_transcript"):
            is_final = event.get("is_final", False) or event.get("speech_final", False)

            # Extract transcript text
            if "channel" in event:
                # Original Deepgram format
                alternatives = event.get("channel", {}).get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    return {
                        "transcript": alt.get("transcript", ""),
                        "is_final": is_final,
                        "confidence": alt.get("confidence", 0.0),
                        "words": alt.get("words", []),
                        "type": "final" if is_final else "partial",
                    }
            else:
                # Already parsed format
                return {
                    "transcript": event.get("text", ""),
                    "is_final": is_final,
                    "confidence": event.get("confidence", 0.0),
                    "words": event.get("words", []),
                    "type": "final" if is_final else "partial",
                }

        # Handle VAD events
        elif event_type == "SpeechStarted" or event_type == "speech_started":
            return {
                "type": "speech_started",
                "timestamp": event.get("timestamp", 0),
            }

        elif event_type == "UtteranceEnd" or event_type == "utterance_end":
            return {
                "type": "utterance_end",
                "timestamp": event.get("timestamp", 0),
            }

        # Ignore metadata events
        elif event_type == "Metadata" or event_type == "metadata":
            return None

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
            sample_rate=self._stt.sample_rate,
            num_channels=1,
            samples_per_channel=len(audio_data) // 2,  # 16-bit PCM
        )

        await self._stream.push_audio(frame)

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
        """Disconnect from Deepgram service (canonical interface)."""
        logger.info("Disconnecting Deepgram adapter")

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

        # Close STT client
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
            interim_results=True,
            vad_events=True,
            turn_detection=False,
            word_timestamps=False,
            speaker_labels=False,
            language_detection=False,
        )
