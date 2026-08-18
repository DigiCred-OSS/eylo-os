"""Gemini Live API adapter.

Audio: PCM 16kHz in → PCM 24kHz out.
SDK: google-genai (client.aio.live.connect manages WebSocket).
Tool results: session.send_tool_response(FunctionResponse(...))
Session limit: ~10 min (mitigated by context window compression + session resumption).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager

from google import genai
from google.genai import types
from google.genai.live import AsyncSession

from eylo.common.contracts.tool_platform import PlatformTool
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.common.schema_utils import clean_schema_for_gemini
from eylo.sockets.realtime.base import RealtimeAdapter, RealtimeCapabilities
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.events import (
    VENDOR_OUTPUT_SAMPLE_RATE,
    AudioDataEvent,
    ErrorEvent,
    GoAwayEvent,
    InputTranscriptEvent,
    InterruptionEvent,
    OutputTranscriptEvent,
    RealtimeEvent,
    SessionStartedEvent,
    ToolCallEvent,
    TurnCompleteEvent,
)

logger = logging.getLogger(__name__)

# Gemini Live accepts 16kHz PCM mono input
_INPUT_AUDIO_MIME = "audio/pcm;rate=16000"


class GeminiLiveAdapter(RealtimeAdapter):
    def __init__(self, config: RealtimeSessionConfig, *, api_key: str) -> None:
        super().__init__(config)
        self._client = genai.Client(api_key=api_key)
        self._session: AsyncSession | None = None
        self._session_context: AbstractAsyncContextManager[AsyncSession] | None = None
        self._session_started_emitted = False
        self._resumption_handle: str | None = None
        self._pending_tool_names: dict[str, str] = {}  # tool_call_id → tool_name

    @property
    def capabilities(self) -> RealtimeCapabilities:
        return RealtimeCapabilities(
            session_update_mode="reconnect",
            session_resumption=True,
            context_compression=True,
        )

    async def connect(self) -> None:
        live_config = self._build_connect_config()
        self._session_context = self._client.aio.live.connect(
            model=self._config.model,
            config=live_config,
        )
        self._session = await self._session_context.__aenter__()
        # ``google-genai`` consumes setup_complete before yielding AsyncSession.
        # A returned session is therefore the canonical successful handshake.
        self._session_started_emitted = False
        self._connected = True
        logger.info(
            "Gemini Live connected",
            extra={"model": self._config.model},
        )

    async def verify_ready(self) -> None:
        """The SDK returns ``AsyncSession`` only after setup completes."""
        if not self._connected or self._session is None:
            raise RuntimeError("Gemini Live session is not connected.")

    async def disconnect(self) -> None:
        self._connected = False
        self._session_started_emitted = False
        self._pending_tool_names.clear()
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                logger.debug("Gemini session close error ignored")
            self._session_context = None
            self._session = None

    async def send_audio(self, audio_data: bytes) -> None:
        if not self._session:
            return
        await self._session.send_realtime_input(
            audio=types.Blob(data=audio_data, mime_type=_INPUT_AUDIO_MIME)
        )

    async def request_speech(self, text: str) -> None:
        """Trigger one spoken response without exposing policy to the manager."""
        if not self._session:
            raise RuntimeError("Gemini Live session is not connected.")
        quoted = json.dumps(text, ensure_ascii=False)
        await self._session.send_realtime_input(
            text=f"Speak exactly this message, without adding anything: {quoted}"
        )

    async def receive(self) -> AsyncIterator[RealtimeEvent]:
        """Yield events continuously across multiple turns.

        The public SDK iterator represents one complete model turn, so the
        outer loop opens the next iterator after ``turn_complete``. No private
        SDK method is part of this adapter contract.
        """
        if not self._session:
            return
        try:
            if not self._session_started_emitted:
                self._session_started_emitted = True
                yield SessionStartedEvent(session_id="gemini")
            while self._connected and self._session:
                received_message = False
                async for response in self._session.receive():
                    received_message = True
                    events = self._translate(response)
                    if events:
                        logger.debug(
                            "Gemini events: %s",
                            [event.type.value for event in events],
                        )
                    for event in events:
                        yield event
                if not received_message:
                    logger.info("Gemini session stream ended without a message")
                    break
        except Exception as error:
            logger.error(
                "Gemini receive failed",
                extra={"error_type": type(error).__name__},
            )
            yield ErrorEvent(
                message="Gemini receive failed",
                code="receive_error",
                is_recoverable=False,
            )

    async def send_tool_result(self, tool_call_id: str, result: str) -> None:
        if not self._session:
            return
        tool_name = self._pending_tool_names.pop(tool_call_id, tool_call_id)
        await self._session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=tool_call_id,
                    name=tool_name,
                    response={"result": result},
                )
            ]
        )

    async def update_session(
        self,
        *,
        system_prompt: str | None = None,
        tools: list[ToolRecord] | None = None,
        voice: str | None = None,
        temperature: float | None = None,
    ) -> None:
        # Gemini requires reconnect for config changes
        await self.disconnect()
        if system_prompt is not None:
            self._config.system_prompt = system_prompt
        if tools is not None:
            self._config.tools = tools
        if voice is not None:
            self._config.voice = voice
        if temperature is not None:
            self._config.temperature = temperature
        await self.connect()

    # --- Private ---

    def _build_connect_config(self) -> types.LiveConnectConfig:
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(
                parts=[types.Part(text=self._config.system_prompt)]
            ),
            generation_config=(
                types.GenerationConfig(temperature=self._config.temperature)
                if self._config.temperature is not None
                else None
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._config.voice
                    )
                ),
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        # Tools
        tool_decls = self._format_tools()
        if tool_decls:
            config.tools = tool_decls

        # Session resumption
        if self._resumption_handle:
            config.session_resumption = types.SessionResumptionConfig(
                handle=self._resumption_handle
            )

        # Context window compression (D013)
        if self._config.is_context_compression_enabled:
            compression = types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            )
            if self._config.context_compression_trigger_tokens:
                compression.trigger_tokens = (
                    self._config.context_compression_trigger_tokens
                )
            config.context_window_compression = compression

        return config

    def _format_tools(self) -> list[types.Tool] | None:
        """Convert platform tools to Gemini SDK ``types.Tool`` objects."""
        if not self._config.tools:
            return None

        declarations: list[types.FunctionDeclaration] = []

        for tool in self._config.tools:
            try:
                if not tool.llm_config:
                    logger.warning("Tool %s has no llm_config, skipping", tool.id)
                    continue

                platform_tool = tool.llm_config
                if not isinstance(platform_tool, PlatformTool):
                    logger.error(
                        "Unexpected llm_config type for tool %s: %s",
                        tool.id,
                        type(tool.llm_config),
                    )
                    continue

                parameters = clean_schema_for_gemini(
                    platform_tool.input_schema.to_json_schema()
                )
                declarations.append(
                    types.FunctionDeclaration(
                        name=platform_tool.name,
                        description=platform_tool.description,
                        parameters=parameters,
                    )
                )
            except Exception as error:
                logger.error(
                    "Tool transformation failed tool_id=%s error_type=%s",
                    tool.id,
                    type(error).__name__,
                )
                continue

        if not declarations:
            return None

        return [types.Tool(function_declarations=declarations)]

    def _translate(self, response: object) -> list[RealtimeEvent]:
        """Translate a Gemini server message into platform events.

        ``response`` is the return value of ``AsyncSession._receive()`` — not
        part of the public SDK API so its concrete type is unspecified.  We
        inspect it via ``getattr`` throughout.

        A single Gemini event can contain multiple parts (audio + transcript
        simultaneously), so we always return a list.
        """
        events: list[RealtimeEvent] = []

        # Server content — audio, transcripts, interruption, turn complete
        content = getattr(response, "server_content", None)
        if content:
            if content.model_turn:
                for part in content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        events.append(
                            AudioDataEvent(
                                audio=part.inline_data.data,
                                sample_rate=VENDOR_OUTPUT_SAMPLE_RATE,
                            )
                        )

            if (
                hasattr(content, "input_transcription")
                and content.input_transcription
                and content.input_transcription.text
            ):
                events.append(
                    InputTranscriptEvent(
                        text=content.input_transcription.text,
                        is_final=False,
                    )
                )
            if (
                hasattr(content, "output_transcription")
                and content.output_transcription
                and content.output_transcription.text
            ):
                events.append(
                    OutputTranscriptEvent(
                        text=content.output_transcription.text,
                        is_final=False,
                    )
                )
            if getattr(content, "interrupted", None) is True:
                events.append(InterruptionEvent())
            if getattr(content, "turn_complete", None) is True:
                events.append(TurnCompleteEvent())

        # Tool calls
        tool_call = getattr(response, "tool_call", None)
        if tool_call:
            for fc in tool_call.function_calls:
                call_id = getattr(fc, "id", None) or f"{fc.name}_{id(fc):x}"
                self._pending_tool_names[call_id] = fc.name
                events.append(
                    ToolCallEvent(
                        tool_call_id=call_id,
                        tool_name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    )
                )

        # Session resumption handle — Gemini sends updated handles periodically.
        # We store the handle for reconnection but do NOT emit a resumed event
        # here. That event is only emitted after an actual reconnect via GoAway.
        resumption = getattr(response, "session_resumption_update", None)
        if resumption:
            handle = getattr(resumption, "new_handle", None)
            if handle:
                self._resumption_handle = handle

        # GoAway
        go_away = getattr(response, "go_away", None)
        if go_away:
            events.append(
                GoAwayEvent(
                    time_left_ms=getattr(go_away, "time_left_ms", 0),
                )
            )

        # Session started (setup_complete)
        if (
            getattr(response, "setup_complete", None)
            and not self._session_started_emitted
        ):
            self._session_started_emitted = True
            events.append(SessionStartedEvent(session_id="gemini"))

        return events
