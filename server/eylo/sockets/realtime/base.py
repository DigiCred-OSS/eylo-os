"""Abstract base for realtime vendor adapters.

Same pattern as STT/TTS vendors: Factory creates → Manager calls lifecycle methods.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.events import RealtimeEvent


@dataclass(frozen=True, slots=True)
class RealtimeCapabilities:
    """Native behavior exposed by one realtime adapter.

    These facts describe the adapter and vendor path only. They never decide
    whether Eylo-owned policies such as recording, silence handling, or call
    limits are available.
    """

    full_duplex_audio: bool = True
    input_transcription: bool = True
    output_transcription: bool = True
    native_turn_detection: bool = True
    native_interruption: bool = True
    tool_calling: bool = True
    platform_message_speech: bool = True
    session_update_mode: Literal["in_place", "reconnect", "unsupported"] = (
        "unsupported"
    )
    voice_selection: bool = True
    session_resumption: bool = False
    context_compression: bool = False
    input_sample_rates: tuple[int, ...] = (16000,)
    output_sample_rates: tuple[int, ...] = (24000,)


class RealtimeAdapter(abc.ABC):
    """Single-session, single-connection realtime voice adapter.

    Lifecycle: __init__(config) → connect() → send_audio()/receive() → disconnect()
    """

    def __init__(self, config: RealtimeSessionConfig) -> None:
        self._config = config
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    @abc.abstractmethod
    def capabilities(self) -> RealtimeCapabilities:
        """Return native capabilities implemented by this adapter path."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Open vendor WebSocket and send session config."""

    @abc.abstractmethod
    async def verify_ready(self) -> None:
        """Prove the connected vendor accepted this session configuration.

        Verification must not require user audio or consume a conversational
        response. Providers with an explicit acknowledgement wait for it;
        providers whose SDK completes setup during ``connect`` validate that
        established session here.
        """

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Close vendor WebSocket cleanly."""

    @abc.abstractmethod
    async def send_audio(self, audio_data: bytes) -> None:
        """Forward a PCM chunk from the browser to the vendor."""

    @abc.abstractmethod
    async def request_speech(self, text: str) -> None:
        """Ask the connected model to speak one platform-owned message.

        This is the normalized boundary used for greetings, recording
        disclosures, silence reminders, and terminal messages. Vendor adapters
        decide how to trigger one response; call policy stays in the pipeline.
        """

    @abc.abstractmethod
    async def receive(self) -> AsyncIterator[RealtimeEvent]:
        """Yield normalized events from the vendor.

        The manager iterates: ``async for event in adapter.receive(): ...``
        Runs until disconnect() is called or the vendor closes.
        """

    @abc.abstractmethod
    async def send_tool_result(self, tool_call_id: str, result: str) -> None:
        """Return a tool execution result to the vendor."""

    @abc.abstractmethod
    async def update_session(
        self,
        *,
        system_prompt: str | None = None,
        tools: list[ToolRecord] | None = None,
        voice: str | None = None,
        temperature: float | None = None,
    ) -> None:
        """Update session config mid-stream (for agent handoffs).

        Gemini: requires reconnect. OpenAI: sends session.update event.
        """
