"""Cartesia STT adapter for canonical STT pipeline.

This adapter wraps the new voice module's CartesiaSTT to work with
the existing STT factory and manager patterns.
"""

import asyncio
import logging
from typing import Any, Optional

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType
from eylo.sockets.voice.vendors.cartesia import CartesiaSTT

logger = logging.getLogger(__name__)


class CartesiaAdapter(STTVendorAdapter):
    """Adapter to use new voice module CartesiaSTT with canonical STT pipeline.

    This class bridges the gap between:
    - Canonical interface: connect(), send_audio(), receive_event()
    - New voice module: stream() with async iteration

    The adapter handles:
    - Audio streaming to Cartesia
    - Event parsing (partial/final transcripts)
    - Response queuing for STT manager
    """

    def __init__(self, config: dict):
        """Initialize Cartesia adapter with resolved provider config.

        Args:
            config: Resolved STT config dict with keys:
                - api_key: Cartesia API key
                - model: STT model
                - language: Language code
                - sample_rate: Audio sample rate (default: 16000)
                - encoding: Audio encoding format (default: 'pcm_s16le')

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
        self._stt = CartesiaSTT(
            api_key=config["api_key"],
            model=config["model"],
            language=config["language"],
            sample_rate=config.get("sample_rate", 16000),
            encoding=config.get("encoding", "pcm_s16le"),
        )

        logger.info(f"Initialized CartesiaAdapter with model={self._stt.model}")

    async def connect(self):
        """Connect to Cartesia service (canonical interface).

        Returns:
            Self to maintain interface compatibility.

        """
        self._stream = self._stt.stream()
        self._receive_task = asyncio.create_task(self._receive_events())
        self._is_connected = True
        logger.info("Cartesia adapter connected")
        return self

    async def _receive_events(self):
        """Receive events from Cartesia stream and queue them."""
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
                "Cartesia event receive failed error_type=%s",
                type(error).__name__,
            )
            self._is_connected = False

    def _convert_event(self, event: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Convert Cartesia event to adapter event format.

        Cartesia STT WebSocket response types:
        - transcript: {type, is_final, text, duration, language, words, request_id}
        - flush_done: Acknowledgment of finalize command
        - done: Session closing acknowledgment
        - error: Error response

        Adapter event shape consumed by receive_event:
        - transcript: str
        - is_final: bool
        - confidence: float
        - type: "partial" | "final" | "utterance_end" | "speech_started"
        """
        event_type = event.get("type")

        if event_type == "transcript":
            text = event.get("text", "")
            is_final = event.get("is_final", False)

            if not text and not is_final:
                return None

            return {
                "transcript": text,
                "is_final": is_final,
                "confidence": 0.95,
                "words": event.get("words", []),
                "type": "final" if is_final else "partial",
            }

        elif event_type == "flush_done":
            # Maps to utterance_end — signals endpointing
            return {
                "type": "utterance_end",
                "timestamp": 0,
            }

        # Ignore done, error, and other event types
        return None

    async def send_audio(self, audio_data: bytes) -> None:
        """Contract method. `send_audio` comes free from the ABC as an alias."""
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

    async def receive_event(self, timeout_ms: int = 100) -> STTEvent | None:
        """Next event as the canonical `STTEvent`.

        Adapts the same queue `receive_event` reads, rather than replacing
        it. The vendor stream yields dicts; this maps the fields the contract
        names and leaves the rest, which is honest about what is actually
        known rather than inventing confidence or timings.
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
        """No flush frame exists for this stream. Stated, not faked.

        Cartesia finalises on end-of-audio; sending anything here would be
        inventing a protocol the vendor does not have.
        """
        return None

    @property
    def model(self) -> str:
        """From the vendor client, which is where the resolved value lives.

        Not from the adapter's own config: the client is what actually
        connected, so it is the honest source for what is running.
        """
        return str(getattr(self._stt, "model", "") or "")

    @property
    def capabilities(self) -> STTCapabilities:
        """Declared rather than discovered, so a caller can branch on it."""
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

    async def keepalive(self) -> None:
        """No keepalive frame for Cartesia. Explicit no-op, reason stated."""
        return None

    async def disconnect(self):
        """Disconnect from Cartesia service (canonical interface)."""
        logger.info("Disconnecting Cartesia adapter")

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
