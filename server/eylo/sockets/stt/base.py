"""Base contract for STT vendor adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from eylo.sockets.stt.schemas import (
    RetryOptions,
    STTCapabilities,
    STTEvent,
)


class STTVendorAdapter(ABC):
    """Canonical contract implemented by every STT provider adapter."""

    def __init__(self, retry_options: RetryOptions | None = None) -> None:
        """Initialize shared adapter state."""
        self.retry_options = retry_options or RetryOptions()

    @abstractmethod
    async def connect(self) -> object:
        """Establish the vendor connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the vendor connection and release resources."""

    @abstractmethod
    async def send_audio(self, audio_data: bytes) -> None:
        """Send raw audio bytes to the vendor."""

    @abstractmethod
    async def receive_event(self, timeout_ms: int = 100) -> STTEvent | None:
        """Receive the next normalized STT event."""

    @abstractmethod
    async def keepalive(self) -> None:
        """Send a keepalive signal, or no-op if unsupported."""

    @abstractmethod
    async def flush(self) -> None:
        """Flush buffered audio or signal end-of-segment."""

    async def recognize(self, audio_data: bytes) -> list[STTEvent]:
        """Batch-recognize a complete audio buffer when supported."""
        raise NotImplementedError("This STT vendor does not support batch recognition")

    async def prewarm(self) -> None:
        """Optionally pre-establish vendor resources."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the adapter has an active vendor connection."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider identifier."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Vendor model identifier."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Input sample rate expected by the adapter."""

    @property
    @abstractmethod
    def capabilities(self) -> STTCapabilities:
        """Capabilities supported by the adapter."""
