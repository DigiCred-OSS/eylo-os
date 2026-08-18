"""Amazon Nova 2 Sonic bidirectional speech adapter.

The adapter owns Bedrock's event protocol. Eylo's turn, interruption, tool,
recording, and call-lifecycle policy remains in ``pipelines.voice``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable
from typing import Any, TypeVar
from uuid import uuid4

from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient
from aws_sdk_bedrock_runtime.config import Config
from aws_sdk_bedrock_runtime.models import (
    BidirectionalInputPayloadPart,
    InvokeModelWithBidirectionalStreamInputChunk,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from smithy_aws_core.identity import StaticCredentialsResolver

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

_INPUT_AUDIO_CONFIG = {
    "mediaType": "audio/lpcm",
    "sampleRateHertz": 16000,
    "sampleSizeBits": 16,
    "channelCount": 1,
    "audioType": "SPEECH",
    "encoding": "base64",
}
_OUTPUT_AUDIO_CONFIG = {
    "mediaType": "audio/lpcm",
    "sampleRateHertz": VENDOR_OUTPUT_SAMPLE_RATE,
    "sampleSizeBits": 16,
    "channelCount": 1,
    "encoding": "base64",
    "audioType": "SPEECH",
}
_SESSION_LIMIT_SECONDS = 8 * 60
_TURN_BOUNDARY_ROTATION_SECONDS = 7 * 60
_FORCED_ROTATION_SECONDS = 7 * 60 + 45
_SDK_RECEIVE_DRAIN_SECONDS = 5.0

_SDKResult = TypeVar("_SDKResult")


def _consume_detached_sdk_result(task: asyncio.Future[Any]) -> None:
    """Consume a shielded SDK await after Eylo stops waiting for it."""
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as error:
        logger.debug(
            "Detached Amazon Nova receive completed with error_type=%s",
            type(error).__name__,
        )


async def _await_cancellation_unsafe_sdk(
    operation: Awaitable[_SDKResult],
    pending_tasks: set[asyncio.Future[Any]],
) -> _SDKResult:
    """Keep task cancellation out of AWS CRT response futures.

    AWS CRT's response-body callback does not guard ``Future.set_result``
    against cancellation. Shielding its awaitable lets Eylo stop its consumer
    immediately without corrupting the SDK-owned future while the stream
    receives the session-end response.
    """
    task = asyncio.ensure_future(operation)
    pending_tasks.add(task)
    task.add_done_callback(pending_tasks.discard)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        task.add_done_callback(_consume_detached_sdk_result)
        raise


class AmazonNovaSonicAdapter(RealtimeAdapter):
    """Translate Nova Sonic's event stream to Eylo's Realtime contract."""

    def __init__(
        self,
        config: RealtimeSessionConfig,
        *,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None = None,
    ) -> None:
        super().__init__(config)
        sdk_config = Config(
            endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
            region=region,
            aws_access_key_id=access_key_id,
            aws_credentials_identity_resolver=StaticCredentialsResolver(),
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
        )
        self._client = BedrockRuntimeClient(config=sdk_config)
        self._stream: Any | None = None
        self._send_lock = asyncio.Lock()
        self._generation = 0
        self._session_started_emitted = False
        self._prompt_name = ""
        self._audio_content_name = ""
        self._content_metadata: dict[str, dict[str, str]] = {}
        self._text_fragments: dict[str, list[str]] = {}
        self._conversation_history: list[tuple[str, str]] = []
        self._pending_policy_inputs: list[frozenset[str]] = []
        self._sdk_receive_tasks: set[asyncio.Future[Any]] = set()
        self._connected_at = 0.0
        self._rotation_requested = False

    @property
    def capabilities(self) -> RealtimeCapabilities:
        return RealtimeCapabilities(session_update_mode="reconnect")

    async def connect(self) -> None:
        if self._connected:
            return
        self._generation += 1
        self._prompt_name = str(uuid4())
        self._audio_content_name = str(uuid4())
        self._content_metadata.clear()
        self._text_fragments.clear()
        self._session_started_emitted = False
        self._rotation_requested = False

        stream = await self._client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(
                model_id=self._config.model
            )
        )
        self._stream = stream
        try:
            await self._send_initial_events()
        except Exception:
            await stream.input_stream.close()
            self._stream = None
            raise
        self._connected = True
        self._connected_at = time.monotonic()
        logger.info(
            "Amazon Nova 2 Sonic connected",
            extra={"model": self._config.model},
        )

    async def verify_ready(self) -> None:
        """Validate Nova's authenticated stream and ordered session setup.

        Nova emits its first output only after user audio. ``connect`` already
        invokes the model stream and sends the complete session/prompt/audio
        input preamble, so those successful operations are its non-invasive
        readiness proof.
        """
        if not self._connected or self._stream is None:
            raise RuntimeError("Amazon Nova 2 Sonic session is not connected.")

    async def disconnect(self) -> None:
        stream = self._stream
        if stream is None:
            self._connected = False
            self._session_started_emitted = False
            self._pending_policy_inputs.clear()
            return
        self._connected = False
        self._stream = None
        try:
            async with self._send_lock:
                await self._send_event_to_stream(
                    stream,
                    self._content_end(self._audio_content_name),
                )
                await self._send_event_to_stream(
                    stream,
                    {"event": {"promptEnd": {"promptName": self._prompt_name}}},
                )
                await self._send_event_to_stream(
                    stream,
                    {"event": {"sessionEnd": {}}},
                )
        except Exception as error:
            logger.debug(
                "Amazon Nova 2 Sonic close events failed error_type=%s",
                type(error).__name__,
            )
        finally:
            try:
                await stream.input_stream.close()
            except Exception as error:
                logger.debug(
                    "Amazon Nova 2 Sonic input close failed error_type=%s",
                    type(error).__name__,
                )
            await self._drain_sdk_receive_tasks()
            output_stream = getattr(stream, "output_stream", None)
            if output_stream is not None:
                try:
                    await output_stream.close()
                except Exception as error:
                    logger.debug(
                        "Amazon Nova 2 Sonic output close failed error_type=%s",
                        type(error).__name__,
                    )
            self._content_metadata.clear()
            self._text_fragments.clear()
            self._session_started_emitted = False
            self._pending_policy_inputs.clear()

    async def _drain_sdk_receive_tasks(self) -> None:
        """Let native response callbacks settle without cancelling their futures."""
        pending = {task for task in self._sdk_receive_tasks if not task.done()}
        if not pending:
            return
        _, still_pending = await asyncio.wait(
            pending,
            timeout=_SDK_RECEIVE_DRAIN_SECONDS,
        )
        if still_pending:
            logger.warning(
                "Amazon Nova 2 Sonic response drain exceeded %.1fs; "
                "native reads continue in background.",
                _SDK_RECEIVE_DRAIN_SECONDS,
            )

    async def send_audio(self, audio_data: bytes) -> None:
        if not audio_data:
            return
        encoded = base64.b64encode(audio_data).decode("ascii")
        await self._send_event(
            {
                "event": {
                    "audioInput": {
                        "promptName": self._prompt_name,
                        "contentName": self._audio_content_name,
                        "content": encoded,
                    }
                }
            }
        )

    async def request_speech(self, text: str) -> None:
        if not self._connected:
            raise RuntimeError("Amazon Nova 2 Sonic session is not connected.")
        instruction = (
            "Speak exactly the following message, without adding anything: "
            f"{json.dumps(text, ensure_ascii=False)}"
        )
        self._pending_policy_inputs.append(
            frozenset(
                filter(None, {_normalize_text(instruction), _normalize_text(text)})
            )
        )
        await self._send_text_sequence(
            role="USER",
            text=instruction,
            interactive=True,
        )

    async def receive(self) -> AsyncIterator[RealtimeEvent]:
        stream = self._stream
        generation = self._generation
        if stream is None:
            return
        try:
            while self._connected and generation == self._generation:
                rotation_timeout = max(
                    0.0,
                    _FORCED_ROTATION_SECONDS
                    - (time.monotonic() - self._connected_at),
                )
                try:
                    async with asyncio.timeout(rotation_timeout):
                        output = await _await_cancellation_unsafe_sdk(
                            stream.await_output(),
                            self._sdk_receive_tasks,
                        )
                        result = await _await_cancellation_unsafe_sdk(
                            output[1].receive(),
                            self._sdk_receive_tasks,
                        )
                except TimeoutError:
                    self._rotation_requested = True
                    yield GoAwayEvent(time_left_ms=self._rotation_time_left_ms())
                    return
                if generation != self._generation:
                    return
                payload = getattr(getattr(result, "value", None), "bytes_", None)
                if payload:
                    data = json.loads(payload.decode("utf-8"))
                    for event in self._translate(data):
                        yield event
                    continue
                error = self._translate_stream_error(result)
                if error is not None:
                    yield error
        except StopAsyncIteration:
            return
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if self._connected and generation == self._generation:
                logger.error(
                    "Amazon Nova 2 Sonic receive failed error_type=%s",
                    type(error).__name__,
                )
                yield ErrorEvent(
                    message="Amazon Nova 2 Sonic receive failed",
                    code="receive_error",
                    is_recoverable=False,
                )

    async def send_tool_result(self, tool_call_id: str, result: str) -> None:
        content_name = str(uuid4())
        await self._send_events(
            [
                {
                    "event": {
                        "contentStart": {
                            "promptName": self._prompt_name,
                            "contentName": content_name,
                            "interactive": False,
                            "type": "TOOL",
                            "role": "TOOL",
                            "toolResultInputConfiguration": {
                                "toolUseId": tool_call_id,
                                "type": "TEXT",
                                "textInputConfiguration": {
                                    "mediaType": "text/plain"
                                },
                            },
                        }
                    }
                },
                {
                    "event": {
                        "toolResult": {
                            "promptName": self._prompt_name,
                            "contentName": content_name,
                            "content": json.dumps({"result": result}),
                        }
                    }
                },
                self._content_end(content_name),
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
        """Reconnect and replay finalized history for handoffs/config changes."""
        if system_prompt is not None:
            self._config.system_prompt = system_prompt
        if tools is not None:
            self._config.tools = tools
        if voice is not None:
            self._config.voice = voice
        if temperature is not None:
            self._config.temperature = temperature
        await self.disconnect()
        await self.connect()

    async def _send_initial_events(self) -> None:
        inference = {
            "maxTokens": self._require_int("max_tokens"),
            "topP": self._require_float("top_p"),
            "temperature": self._require_float("temperature"),
        }
        session_start: dict[str, Any] = {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": inference,
                    "turnDetectionConfiguration": {
                        "endpointingSensitivity": self._require_string(
                            "endpointing_sensitivity"
                        )
                    },
                }
            }
        }
        prompt_start: dict[str, Any] = {
            "event": {
                "promptStart": {
                    "promptName": self._prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        **_OUTPUT_AUDIO_CONFIG,
                        "voiceId": self._config.voice,
                    },
                }
            }
        }
        tool_config = self._format_tools()
        if tool_config:
            prompt_start["event"]["promptStart"].update(
                {
                    "toolUseOutputConfiguration": {
                        "mediaType": "application/json"
                    },
                    "toolConfiguration": {"tools": tool_config},
                }
            )

        await self._send_events([session_start, prompt_start])
        if self._config.system_prompt.strip():
            await self._send_text_sequence(
                role="SYSTEM",
                text=self._config.system_prompt,
                interactive=False,
            )
        for role, text in self._replayable_history():
            await self._send_text_sequence(
                role=role,
                text=text,
                interactive=False,
            )
        await self._send_event(
            {
                "event": {
                    "contentStart": {
                        "promptName": self._prompt_name,
                        "contentName": self._audio_content_name,
                        "type": "AUDIO",
                        "interactive": True,
                        "role": "USER",
                        "audioInputConfiguration": dict(_INPUT_AUDIO_CONFIG),
                    }
                }
            }
        )

    async def _send_text_sequence(
        self,
        *,
        role: str,
        text: str,
        interactive: bool,
    ) -> None:
        content_name = str(uuid4())
        await self._send_events(
            [
                {
                    "event": {
                        "contentStart": {
                            "promptName": self._prompt_name,
                            "contentName": content_name,
                            "type": "TEXT",
                            "interactive": interactive,
                            "role": role,
                            "textInputConfiguration": {"mediaType": "text/plain"},
                        }
                    }
                },
                {
                    "event": {
                        "textInput": {
                            "promptName": self._prompt_name,
                            "contentName": content_name,
                            "content": text,
                        }
                    }
                },
                self._content_end(content_name),
            ]
        )

    async def _send_event(self, event: dict[str, Any]) -> None:
        await self._send_events([event])

    async def _send_events(self, events: list[dict[str, Any]]) -> None:
        stream = self._stream
        if stream is None:
            raise RuntimeError("Amazon Nova 2 Sonic session is not connected.")
        async with self._send_lock:
            for event in events:
                await self._send_event_to_stream(stream, event)

    @staticmethod
    async def _send_event_to_stream(stream: Any, event: dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
        await stream.input_stream.send(
            InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=payload)
            )
        )

    def _content_end(self, content_name: str) -> dict[str, Any]:
        return {
            "event": {
                "contentEnd": {
                    "promptName": self._prompt_name,
                    "contentName": content_name,
                }
            }
        }

    def _format_tools(self) -> list[dict[str, Any]]:
        declarations = extract_openai_function_declarations(self._config.tools)
        return [
            {
                "toolSpec": {
                    "name": declaration["name"],
                    "description": declaration.get("description", ""),
                    "inputSchema": {
                        "json": json.dumps(declaration.get("parameters", {}))
                    },
                }
            }
            for declaration in declarations
        ]

    def _translate(self, data: dict[str, Any]) -> list[RealtimeEvent]:
        event_wrapper = data.get("event")
        if not isinstance(event_wrapper, dict) or not event_wrapper:
            return []
        event_name, payload = next(iter(event_wrapper.items()))
        if not isinstance(payload, dict):
            return []

        if event_name in {"sessionStart", "usageEvent"}:
            if self._session_started_emitted:
                return []
            self._session_started_emitted = True
            return [SessionStartedEvent(session_id=str(payload.get("sessionId", "")))]
        if event_name == "completionStart":
            return []
        if event_name == "contentStart":
            self._remember_content_metadata(payload)
            return []
        if event_name == "textOutput":
            content_id = str(payload.get("contentId", ""))
            content = payload.get("content")
            if content_id and isinstance(content, str):
                self._text_fragments.setdefault(content_id, []).append(content)
            return []
        if event_name == "audioOutput":
            encoded = payload.get("content")
            if not isinstance(encoded, str):
                return []
            try:
                audio = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                return [
                    ErrorEvent(
                        message="Amazon Nova 2 Sonic returned invalid audio",
                        code="invalid_audio",
                        is_recoverable=True,
                    )
                ]
            return (
                [AudioDataEvent(audio=audio, sample_rate=VENDOR_OUTPUT_SAMPLE_RATE)]
                if audio
                else []
            )
        if event_name == "toolUse":
            return [self._translate_tool_call(payload)]
        if event_name == "contentEnd":
            return self._translate_content_end(payload)
        if event_name == "completionEnd":
            stop_reason = str(payload.get("stopReason", ""))
            if stop_reason not in {"END_TURN", "INTERRUPTED"}:
                return []
            events: list[RealtimeEvent] = [TurnCompleteEvent()]
            if (
                not self._rotation_requested
                and time.monotonic() - self._connected_at
                >= _TURN_BOUNDARY_ROTATION_SECONDS
            ):
                self._rotation_requested = True
                events.append(
                    GoAwayEvent(time_left_ms=self._rotation_time_left_ms())
                )
            return events
        if event_name == "error":
            return [
                ErrorEvent(
                    message="Amazon Nova 2 Sonic reported an error",
                    code=str(payload.get("code", "provider_error")),
                    is_recoverable=False,
                )
            ]
        return []

    def _remember_content_metadata(self, payload: dict[str, Any]) -> None:
        content_id = str(payload.get("contentId", ""))
        if not content_id:
            return
        additional = payload.get("additionalModelFields")
        generation_stage = ""
        if isinstance(additional, str):
            try:
                parsed = json.loads(additional)
                generation_stage = str(parsed.get("generationStage", ""))
            except json.JSONDecodeError:
                logger.debug("Amazon Nova 2 Sonic sent invalid model metadata")
        self._content_metadata[content_id] = {
            "role": str(payload.get("role", "")),
            "type": str(payload.get("type", "")),
            "generation_stage": generation_stage,
        }

    def _translate_content_end(
        self, payload: dict[str, Any]
    ) -> list[RealtimeEvent]:
        events: list[RealtimeEvent] = []
        content_id = str(payload.get("contentId", ""))
        metadata = self._content_metadata.pop(content_id, {})
        text = "".join(self._text_fragments.pop(content_id, [])).strip()
        if text and metadata.get("generation_stage") == "FINAL":
            role = metadata.get("role")
            if role == "USER":
                normalized = _normalize_text(text)
                matching_policy = next(
                    (
                        candidates
                        for candidates in self._pending_policy_inputs
                        if normalized in candidates
                    ),
                    None,
                )
                if matching_policy is not None:
                    self._pending_policy_inputs.remove(matching_policy)
                else:
                    self._conversation_history.append(("USER", text))
                    events.append(InputTranscriptEvent(text=text, is_final=True))
            elif role == "ASSISTANT":
                self._conversation_history.append(("ASSISTANT", text))
                events.append(OutputTranscriptEvent(text=text, is_final=True))
        if payload.get("stopReason") == "INTERRUPTED":
            events.append(InterruptionEvent())
        return events

    @staticmethod
    def _translate_tool_call(payload: dict[str, Any]) -> ToolCallEvent:
        raw_arguments = payload.get("content", {})
        if isinstance(raw_arguments, str):
            try:
                raw_arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                raw_arguments = {}
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        return ToolCallEvent(
            tool_call_id=str(payload.get("toolUseId", "")),
            tool_name=str(payload.get("toolName", "")),
            arguments=arguments,
        )

    @staticmethod
    def _translate_stream_error(result: object) -> ErrorEvent | None:
        value = getattr(result, "value", None)
        if value is None:
            return None
        result_name = type(result).__name__
        recoverable = result_name in {
            "InvokeModelWithBidirectionalStreamOutputInternalServerException",
            "InvokeModelWithBidirectionalStreamOutputModelTimeoutException",
            "InvokeModelWithBidirectionalStreamOutputServiceUnavailableException",
            "InvokeModelWithBidirectionalStreamOutputThrottlingException",
        }
        code = result_name.removeprefix(
            "InvokeModelWithBidirectionalStreamOutput"
        ).removesuffix("Exception")
        return ErrorEvent(
            message="Amazon Nova 2 Sonic stream error",
            code=code or "stream_error",
            is_recoverable=recoverable,
        )

    def _replayable_history(self) -> list[tuple[str, str]]:
        for index, (role, _) in enumerate(self._conversation_history):
            if role == "USER":
                return self._conversation_history[index:]
        return []

    def _rotation_time_left_ms(self) -> int:
        elapsed = time.monotonic() - self._connected_at
        return max(0, int((_SESSION_LIMIT_SECONDS - elapsed) * 1000))

    def _require_string(self, field_name: str) -> str:
        value = getattr(self._config, field_name)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"Amazon Nova 2 Sonic requires {field_name}.")
        return value

    def _require_int(self, field_name: str) -> int:
        value = getattr(self._config, field_name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError(f"Amazon Nova 2 Sonic requires {field_name}.")
        return value

    def _require_float(self, field_name: str) -> float:
        value = getattr(self._config, field_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(f"Amazon Nova 2 Sonic requires {field_name}.")
        return float(value)


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()
