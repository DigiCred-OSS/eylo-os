"""OpenAI Realtime API adapter.

Raw WebSocket to wss://api.openai.com/v1/realtime.
Audio: PCM 24kHz in/out (browser sends 16kHz — resample in send_audio).
Events are JSON frames over WebSocket.
"""

from __future__ import annotations

import base64
import enum
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import websockets

from eylo.audio.ops import StreamingResampler
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.llm.vendors.openai_utils import (
    extract_openai_function_declarations,
)
from eylo.sockets.realtime.base import RealtimeAdapter, RealtimeCapabilities
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.events import (
    VENDOR_OUTPUT_SAMPLE_RATE,
    AudioDataEvent,
    ErrorEvent,
    InputTranscriptEvent,
    OutputTranscriptEvent,
    RealtimeEvent,
    SessionStartedEvent,
    ToolCallEvent,
    TurnCompleteEvent,
    UserSpeechStartedEvent,
)

logger = logging.getLogger(__name__)

_OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"

# Current Realtime WebSocket sessions use 24 kHz signed PCM for both directions.
_PCM_AUDIO_FORMAT = {"type": "audio/pcm", "rate": 24000}


class _OAIEvent(str, enum.Enum):
    """Server-sent event types from OpenAI Realtime API."""

    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    AUDIO_DELTA = "response.output_audio.delta"
    LEGACY_AUDIO_DELTA = "response.audio.delta"
    TRANSCRIPT_DELTA = "response.output_audio_transcript.delta"
    LEGACY_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    TRANSCRIPT_DONE = "response.output_audio_transcript.done"
    LEGACY_TRANSCRIPT_DONE = "response.audio_transcript.done"
    INPUT_TRANSCRIPTION_DONE = "conversation.item.input_audio_transcription.completed"
    OUTPUT_ITEM_ADDED = "response.output_item.added"
    OUTPUT_ITEM_DONE = "response.output_item.done"
    FUNCTION_CALL_DONE = "response.function_call_arguments.done"
    RESPONSE_DONE = "response.done"
    SPEECH_STARTED = "input_audio_buffer.speech_started"
    ERROR = "error"


class _OAIClientEvent(str, enum.Enum):
    """Client-sent event types to OpenAI Realtime API."""

    INPUT_AUDIO_APPEND = "input_audio_buffer.append"
    SESSION_UPDATE = "session.update"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    RESPONSE_CREATE = "response.create"


def _resample_16k_to_24k(audio_16k: bytes, resampler: StreamingResampler) -> bytes:
    """Resample PCM 16-bit mono from 16kHz to 24kHz.

    OpenAI Realtime expects 24kHz input; browser sends 16kHz via WebRTC.
    Ratio: 3/2 (up=3, down=2).
    """
    return resampler.process(audio_16k)


class OpenAIRealtimeAdapter(RealtimeAdapter):
    def __init__(self, config: RealtimeSessionConfig, *, api_key: str) -> None:
        super().__init__(config)
        self._api_key = api_key
        self._ws: websockets.ClientConnection | None = None
        self._pending_tool_names: dict[str, str] = {}
        # Per-session resampler — never share across sessions.
        self._upsampler = StreamingResampler(from_rate=16000, to_rate=24000)

    @property
    def capabilities(self) -> RealtimeCapabilities:
        return RealtimeCapabilities(session_update_mode="in_place")

    async def connect(self) -> None:
        url = f"{_OPENAI_REALTIME_URL}?model={self._config.model}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        self._ws = await websockets.connect(url, additional_headers=headers)
        await self._send_session_update()
        self._connected = True
        logger.info(
            "OpenAI Realtime connected",
            extra={"model": self._config.model},
        )

    async def verify_ready(self) -> None:
        """Wait for OpenAI to accept the session update sent by ``connect``."""
        if not self._connected or not self._ws:
            raise RuntimeError("OpenAI Realtime session is not connected.")
        while True:
            data = json.loads(await self._ws.recv())
            event_type = data.get("type")
            if event_type == _OAIEvent.SESSION_UPDATED:
                return
            if event_type == _OAIEvent.ERROR:
                raise RuntimeError("OpenAI Realtime rejected the session config.")

    async def disconnect(self) -> None:
        self._connected = False
        self._pending_tool_names.clear()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                logger.debug("OpenAI WebSocket close error ignored")
            self._ws = None

    async def send_audio(self, audio_data: bytes) -> None:
        if not self._ws:
            return
        # OpenAI expects 24kHz — resample from browser's 16kHz
        resampled = _resample_16k_to_24k(audio_data, self._upsampler)
        encoded = base64.b64encode(resampled).decode("ascii")
        await self._ws.send(
            json.dumps(
                {
                    "type": _OAIClientEvent.INPUT_AUDIO_APPEND,
                    "audio": encoded,
                }
            )
        )

    async def request_speech(self, text: str) -> None:
        """Trigger one audio response with per-response instructions."""
        if not self._ws:
            raise RuntimeError("OpenAI Realtime session is not connected.")
        await self._ws.send(
            json.dumps(
                {
                    "type": _OAIClientEvent.RESPONSE_CREATE,
                    "response": {
                        "instructions": (
                            "Speak exactly the following message, without adding "
                            f"anything: {text}"
                        )
                    },
                }
            )
        )

    async def receive(self) -> AsyncIterator[RealtimeEvent]:
        if not self._ws:
            return
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                for event in self._translate(data):
                    yield event
        except websockets.ConnectionClosed:
            logger.warning("OpenAI WebSocket closed")
            yield ErrorEvent(
                message="OpenAI WebSocket closed",
                code="connection_closed",
                is_recoverable=False,
            )
        except Exception as error:
            logger.error(
                "OpenAI receive failed",
                extra={"error_type": type(error).__name__},
            )
            yield ErrorEvent(
                message="OpenAI receive failed",
                code="receive_error",
                is_recoverable=False,
            )

    async def send_tool_result(self, tool_call_id: str, result: str) -> None:
        if not self._ws:
            return
        await self._ws.send(
            json.dumps(
                {
                    "type": _OAIClientEvent.CONVERSATION_ITEM_CREATE,
                    "item": {
                        "type": "function_call_output",
                        "call_id": tool_call_id,
                        "output": result,
                    },
                }
            )
        )
        # After sending tool result, request a new response
        await self._ws.send(json.dumps({"type": _OAIClientEvent.RESPONSE_CREATE}))

    async def update_session(
        self,
        *,
        system_prompt: str | None = None,
        tools: list[ToolRecord] | None = None,
        voice: str | None = None,
        temperature: float | None = None,
    ) -> None:
        """OpenAI supports session.update without reconnect."""
        if not self._ws:
            return
        update: dict[str, Any] = {}
        if system_prompt is not None:
            update["instructions"] = system_prompt
            self._config.system_prompt = system_prompt
        if tools is not None:
            update["tools"] = self._format_tools(tools)
            self._config.tools = tools
        if voice is not None:
            self._config.voice = voice
        if temperature is not None:
            raise ValueError("OpenAI Realtime does not support temperature.")
        audio_update: dict[str, Any] = {}
        if voice is not None:
            audio_update["output"] = {"voice": voice}
        if audio_update:
            update["audio"] = audio_update
        if update:
            update["type"] = "realtime"
            await self._ws.send(
                json.dumps(
                    {
                        "type": _OAIClientEvent.SESSION_UPDATE,
                        "session": update,
                    }
                )
            )

    # --- Private ---

    async def _send_session_update(self) -> None:
        if not self._ws:
            return
        session_config: dict[str, Any] = {
            "type": "realtime",
            "instructions": self._config.system_prompt,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": dict(_PCM_AUDIO_FORMAT),
                },
                "output": {
                    "format": dict(_PCM_AUDIO_FORMAT),
                    "voice": self._config.voice,
                },
            },
        }
        audio_input = session_config["audio"]["input"]
        if self._config.input_transcription_model is not None:
            audio_input["transcription"] = {
                "model": self._config.input_transcription_model
            }
        turn_detection: dict[str, Any] = {
            "type": "server_vad",
            "create_response": True,
            "interrupt_response": True,
        }
        if self._config.vad_threshold is not None:
            turn_detection["threshold"] = self._config.vad_threshold
        if self._config.vad_silence_ms is not None:
            turn_detection["silence_duration_ms"] = self._config.vad_silence_ms
        audio_input["turn_detection"] = turn_detection
        tools = self._format_tools()
        if tools:
            session_config["tools"] = tools
        await self._ws.send(
            json.dumps(
                {
                    "type": _OAIClientEvent.SESSION_UPDATE,
                    "session": session_config,
                }
            )
        )

    def _format_tools(
        self, tools: list[ToolRecord] | None = None
    ) -> list[dict[str, Any]]:
        """Convert platform tools to OpenAI Realtime API format.

        Delegates extraction to ``extract_openai_function_declarations``
        (shared with Chat Completions and Responses adapters) and wraps
        each declaration in the flat ``{"type": "function", ...}`` format
        used by the Realtime API (no ``strict`` flag, no ``function`` nesting).
        """
        tool_list = tools if tools is not None else self._config.tools
        declarations = extract_openai_function_declarations(tool_list)
        return [{"type": "function", **d} for d in declarations]

    def _translate(self, data: dict[str, Any]) -> list[RealtimeEvent]:
        """Translate one OpenAI server event into platform events."""
        events: list[RealtimeEvent] = []
        event_type = data.get("type", "")

        if event_type == _OAIEvent.SESSION_CREATED:
            events.append(
                SessionStartedEvent(
                    session_id=data.get("session", {}).get("id", ""),
                )
            )

        elif event_type in {_OAIEvent.AUDIO_DELTA, _OAIEvent.LEGACY_AUDIO_DELTA}:
            audio_bytes = base64.b64decode(data.get("delta", ""))
            if audio_bytes:
                events.append(
                    AudioDataEvent(
                        audio=audio_bytes, sample_rate=VENDOR_OUTPUT_SAMPLE_RATE
                    )
                )

        elif event_type in {
            _OAIEvent.TRANSCRIPT_DELTA,
            _OAIEvent.LEGACY_TRANSCRIPT_DELTA,
        }:
            events.append(
                OutputTranscriptEvent(
                    text=data.get("delta", ""),
                    is_final=False,
                )
            )

        elif event_type in {
            _OAIEvent.TRANSCRIPT_DONE,
            _OAIEvent.LEGACY_TRANSCRIPT_DONE,
        }:
            events.append(
                OutputTranscriptEvent(
                    text=data.get("transcript", ""),
                    is_final=True,
                )
            )

        elif event_type == _OAIEvent.INPUT_TRANSCRIPTION_DONE:
            events.append(
                InputTranscriptEvent(
                    text=data.get("transcript", ""),
                    is_final=True,
                )
            )

        elif event_type in {_OAIEvent.OUTPUT_ITEM_ADDED, _OAIEvent.OUTPUT_ITEM_DONE}:
            item = data.get("item", {})
            if item.get("type") == "function_call":
                call_id = item.get("call_id")
                name = item.get("name")
                if call_id and name:
                    self._pending_tool_names[call_id] = name

        elif event_type == _OAIEvent.FUNCTION_CALL_DONE:
            try:
                arguments = json.loads(data.get("arguments", "{}"))
            except json.JSONDecodeError:
                logger.warning("Malformed tool arguments from OpenAI")
                arguments = {}
            call_id = data.get("call_id", "")
            events.append(
                ToolCallEvent(
                    tool_call_id=call_id,
                    tool_name=(
                        data.get("name")
                        or self._pending_tool_names.pop(call_id, "")
                    ),
                    arguments=arguments,
                )
            )

        elif event_type == _OAIEvent.RESPONSE_DONE:
            # P-F07: response.done fires per response object, not per
            # conversational turn.  When the response contains function calls,
            # the vendor will issue another response after tool results —
            # only emit TurnComplete for the final response.
            response = data.get("response", {})
            response_status = response.get("status")
            if response_status in {"failed", "incomplete"}:
                events.append(
                    ErrorEvent(
                        message="OpenAI Realtime response did not complete",
                        code=f"response_{response_status}",
                        is_recoverable=True,
                    )
                )
            response_output = response.get("output", [])
            has_pending_tool_calls = any(
                item.get("type") == "function_call" for item in response_output
            )
            if (
                response_status is not None and response_status != "completed"
            ) or not has_pending_tool_calls:
                events.append(TurnCompleteEvent())

        elif event_type == _OAIEvent.SPEECH_STARTED:
            events.append(UserSpeechStartedEvent())

        elif event_type == _OAIEvent.ERROR:
            err = data.get("error", {})
            events.append(
                ErrorEvent(
                    message=err.get("message", "Unknown error"),
                    code=err.get("code", ""),
                    is_recoverable=err.get("type") != "invalid_request_error",
                )
            )

        return events
