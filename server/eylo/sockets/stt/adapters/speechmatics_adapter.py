"""Speechmatics STT adapter for canonical STT pipeline.

This adapter wraps the new voice module's SpeechmaticsSTT to work with
the existing STT factory and manager patterns.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType
from eylo.sockets.voice.vendors.speechmatics import (
    SpeechmaticsSTT,
    SpeechmaticsSTTStream,
)

logger = logging.getLogger(__name__)


class SpeechmaticsAdapter(STTVendorAdapter):
    """Adapter to use new voice module SpeechmaticsSTT with canonical STT pipeline.

    This class bridges the gap between:
    - Canonical interface: connect(), send_audio(), receive_event()
    - New voice module: stream() with async iteration

    The adapter handles:
    - Audio streaming to Speechmatics
    - Event parsing (transcripts, partials, speaker diarization)
    - Response queuing for STT manager
    """

    def __init__(self, config: dict):
        """Initialize Speechmatics adapter with resolved provider config.

        Args:
            config: Resolved STT config dict with keys:
                - api_key: Speechmatics API key
                - language: Language code
                - sample_rate: Audio sample rate
                - enable_partials: Enable interim results
                - enable_entities: Enable entity extraction
                - max_delay: Maximum delay in seconds
                - diarization: Enable speaker diarization
                - custom_vocabulary: List of custom words

        """
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._is_connected = False
        self._stream: Optional[SpeechmaticsSTTStream] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # Initialize new voice module STT
        self._stt = SpeechmaticsSTT(
            language=config["language"],
            enable_partials=config.get("enable_partials", True),
            enable_entities=config.get("enable_entities", False),
            max_delay=config.get("max_delay", 2.0),
            sample_rate=config.get("sample_rate", 16000),
            api_key=config["api_key"],
            diarization=config.get("diarization"),
            custom_vocabulary=config.get("custom_vocabulary"),
        )

        logger.info(
            f"Initialized SpeechmaticsAdapter with language={self._stt.language}"
        )

    async def connect(self):
        """Connect to Speechmatics service (canonical interface).

        Returns:
            Self to maintain interface compatibility.

        """
        # Create stream
        self._stream = self._stt.stream()

        # Start background task to receive events
        self._receive_task = asyncio.create_task(self._receive_events())

        self._is_connected = True
        logger.info("Speechmatics adapter connected")
        return self

    async def _receive_events(self):
        """Receive events from Speechmatics stream and queue them.

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
                "Speechmatics event receive failed error_type=%s",
                type(error).__name__,
            )
            self._is_connected = False

    def _convert_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert voice module event format to adapter event format.

        Args:
            event: Event from voice module.

        Returns:
            Event in adapter event format or None if should be filtered.

        Speechmatics event types:
        - message: "AddPartialTranscript" - interim results
        - message: "AddTranscript" - final results
        - message: "RecognitionStarted" - connection established
        - message: "AudioAdded" - audio chunk acknowledged
        - message: "EndOfTranscript" - transcription complete
        - message: "Error" - error occurred

        Adapter event shape consumed by receive_event:
        - transcript: str
        - is_final: bool
        - confidence: float
        - type: "speech_started" | "utterance_end" | etc.

        """
        message_type = event.get("message")

        # Handle partial transcripts (interim results)
        if message_type == "AddPartialTranscript":
            results = event.get("results", [])
            if results:
                result = results[0]
                alternatives = result.get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    return {
                        "transcript": alt.get("content", ""),
                        "is_final": False,
                        "confidence": alt.get("confidence", 0.0),
                        "type": "partial",
                        "speaker": result.get("speaker"),  # Speaker diarization
                        "start_time": result.get("start_time"),
                        "end_time": result.get("end_time"),
                    }

        # Handle final transcripts
        elif message_type == "AddTranscript":
            results = event.get("results", [])
            if results:
                result = results[0]
                alternatives = result.get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    return {
                        "transcript": alt.get("content", ""),
                        "is_final": True,
                        "confidence": alt.get("confidence", 1.0),
                        "type": "final",
                        "speaker": result.get("speaker"),  # Speaker diarization
                        "start_time": result.get("start_time"),
                        "end_time": result.get("end_time"),
                        "entities": alt.get("entities", []),  # Entity extraction
                    }

        # Handle connection events
        elif message_type == "RecognitionStarted":
            return {
                "type": "recognition_started",
                "id": event.get("id"),
            }

        # Handle end of transcript
        elif message_type == "EndOfTranscript":
            return {
                "type": "end_of_transcript",
            }

        # Ignore audio acknowledgments
        elif message_type == "AudioAdded":
            return None

        # Handle errors
        elif message_type == "Error":
            logger.error("Speechmatics STT provider error")
            return {
                "type": "error",
                "error": event.get("reason", "Unknown error"),
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
        """Disconnect from Speechmatics service (canonical interface)."""
        logger.info("Disconnecting Speechmatics adapter")

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
            vad_events=False,
            turn_detection=False,
            word_timestamps=False,
            speaker_labels=True,
            language_detection=False,
        )
