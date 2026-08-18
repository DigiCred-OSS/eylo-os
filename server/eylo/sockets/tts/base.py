"""Provider-neutral contracts for the `tts` socket."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from eylo.sockets.tts.schemas import (
    RetryOptions,
    TTSAudioChunk,
    TTSAudioFormat,
    TTSCapabilities,
    TTSConfig,
)

T = TypeVar("T")


class TTSVendorAdapter(ABC):
    """Canonical contract implemented by every TTS provider adapter."""

    def __init__(
        self,
        config: TTSConfig,
        retry_options: RetryOptions | None = None,
    ) -> None:
        self._contract_config = config
        self._retry_options = retry_options or config.retry
        self._text_buffer: list[str] = []

    @abstractmethod
    async def connect(self) -> object:
        """Establish a vendor connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the vendor connection and release resources."""

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Send text to synthesize for the current turn."""

    @abstractmethod
    async def receive_audio(self) -> bytes | TTSAudioChunk | None:
        """Receive the next synthesized audio chunk, if available."""

    @abstractmethod
    async def handle_interruption(self) -> None:
        """Cancel synthesis and clear vendor-owned audio/text buffers."""

    @abstractmethod
    async def flush(self) -> None:
        """Finalize text input for the current turn."""

    @abstractmethod
    async def keepalive(self) -> None:
        """Keep the vendor connection alive."""

    async def synthesize(self, text: str) -> AsyncIterator[bytes | TTSAudioChunk]:
        """Batch synthesize text through the streaming contract."""
        await self.send_text(text)
        await self.flush()
        while True:
            chunk = await self.receive_audio()
            if chunk is None:
                break
            yield chunk

    def prewarm(self) -> None:
        """Optionally warm a vendor connection before first use."""

    @property
    def is_turn_complete(self) -> bool:
        """Whether the vendor has signalled the end of the current turn."""
        return False

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the adapter is connected."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Return the output sample rate."""

    @property
    def output_audio_format(self) -> TTSAudioFormat:
        """Return the actual raw media emitted by this adapter."""
        return TTSAudioFormat(
            container="raw",
            encoding=self._contract_config.encoding,
            sample_rate=self.sample_rate,
        )

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the vendor model identifier."""

    @property
    @abstractmethod
    def capabilities(self) -> TTSCapabilities:
        """Return static vendor capabilities."""

    def _buffer_text(self, text: str) -> None:
        if text:
            self._text_buffer.append(text)

    def _get_buffered_text(self) -> str:
        text = "".join(self._text_buffer)
        self._text_buffer.clear()
        return text

    async def _run_with_retries(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        retry_options: RetryOptions | None = None,
    ) -> T:
        options = retry_options or self._retry_options
        attempt = 0
        while True:
            try:
                return await asyncio.wait_for(
                    operation(),
                    timeout=options.timeout_seconds,
                )
            except Exception:
                if attempt >= options.max_retries:
                    raise
                attempt += 1
                await asyncio.sleep(options.retry_interval_seconds)
