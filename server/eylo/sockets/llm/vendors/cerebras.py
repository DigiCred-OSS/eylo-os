"""Cerebras vendor adapter implementation.

Cerebras Inference provides an OpenAI-compatible Chat Completions API
(``/v1/chat/completions``) with the same message format, tool calling format,
and response structure.  This adapter therefore extends ``OpenAIAdapter`` and
overrides only what differs:

1. **Client** — ``AsyncCerebras`` instead of ``AsyncOpenAI``.
2. **Inference parameters** — Cerebras-specific flags per model:
   - ``clear_thinking`` for ``zai-glm-4.7`` (default False for agentic workflows).
   - ``reasoning_effort`` passthrough for ``gpt-oss-120b``.
   - ``parallel_tool_calls`` support for ``zai-glm-4.7``.
3. **Response metadata** — Cerebras returns ``time_info`` (queue_time,
   prompt_time, completion_time) which is captured in ``LLMResponse.metadata``.

References:
- Cerebras Inference Docs: https://inference-docs.cerebras.ai/introduction
- Chat Completions API: https://inference-docs.cerebras.ai/api-reference/chat-completions
- Tool Calling: https://inference-docs.cerebras.ai/capabilities/tool-use

"""

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List

from cerebras.cloud.sdk import AsyncCerebras, RateLimitError

from eylo.common.contracts.messages import MessageInDb
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.llm.config import configured_generation_params, require_model
from eylo.sockets.llm.schemas import LLMResponse
from eylo.sockets.llm.vendors.openai import OpenAIAdapter

logger = logging.getLogger(__name__)

# Models that support the ``clear_thinking`` parameter.
_CLEAR_THINKING_MODELS = {"zai-glm-4.7"}

# Models that support the ``reasoning_effort`` parameter.
_REASONING_EFFORT_MODELS = {"gpt-oss-120b"}

# Models that support ``parallel_tool_calls``.
_PARALLEL_TOOL_CALL_MODELS = {"zai-glm-4.7"}

# Retry configuration for 429 rate-limit errors.
_MAX_RETRIES = 3
_BASE_DELAY_S = 1.0  # doubles each retry: 1s → 2s → 4s
_MAX_DELAY_S = 10.0


class CerebrasAdapter(OpenAIAdapter):
    """Cerebras Inference adapter using the OpenAI-compatible API.

    Since Cerebras exposes an OpenAI-compatible Chat Completions endpoint,
    this adapter extends ``OpenAIAdapter`` and overrides only the client
    constructor and inference methods to inject Cerebras-specific parameters.

    Inherited from OpenAIAdapter (unchanged):
    - ``transform_messages_to_vendor()``
    - ``transform_response_to_platform()``
    - Message transition handlers
    - Streaming chunk accumulation
    """

    vendor_name = "cerebras"

    # The adapter creates a client per inference call; it does not own a
    # process-lifetime client or connection lifecycle.

    def get_client(self) -> AsyncCerebras:
        """Get authenticated Cerebras client."""
        return AsyncCerebras(api_key=self._api_key)

    # ── Schema cleaning ─────────────────────────────────────────

    # Fields that Cerebras rejects on array schemas.
    _CEREBRAS_UNSUPPORTED_ARRAY_FIELDS = {"minItems", "maxItems"}

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform tools then strip fields unsupported by Cerebras.

        Cerebras uses an OpenAI-compatible API but rejects certain JSON Schema
        keywords (``minItems``, ``maxItems``) on array types.  We delegate to
        the parent ``OpenAIAdapter.transform_tools_to_vendor`` and then clean
        the resulting schemas.
        """
        vendor_tools = super().transform_tools_to_vendor(tools)
        return [self._clean_schema_for_cerebras(t) for t in vendor_tools]

    def _clean_schema_for_cerebras(self, obj: Any) -> Any:
        """Recursively strip fields Cerebras rejects from a tool dict."""
        if isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                if key in self._CEREBRAS_UNSUPPORTED_ARRAY_FIELDS:
                    continue
                cleaned[key] = self._clean_schema_for_cerebras(value)
            return cleaned
        if isinstance(obj, list):
            return [self._clean_schema_for_cerebras(item) for item in obj]
        return obj

    # ── Cerebras-specific request parameter helpers ──────────────

    def _build_cerebras_params(
        self,
        model: str,
        llm_config: Dict[str, Any],
        has_tools: bool,
    ) -> Dict[str, Any]:
        """Build Cerebras-specific parameters that extend the base request.

        Args:
            model: The model identifier (e.g. ``gpt-oss-120b``).
            llm_config: Agent's LLM configuration dict.
            has_tools: Whether tools are included in the request.

        Returns:
            Dict of extra keyword arguments to pass to the API call.

        """
        extra: Dict[str, Any] = {}

        # zai-glm-4.7: preserve reasoning from previous turns for agentic
        # workflows where past tool-call reasoning informs future calls.
        if model in _CLEAR_THINKING_MODELS:
            extra["clear_thinking"] = llm_config.get("clear_thinking", False)

        # gpt-oss-120b: optional reasoning effort control.
        if model in _REASONING_EFFORT_MODELS:
            reasoning_effort = llm_config.get("reasoning_effort")
            if reasoning_effort is not None:
                extra["reasoning_effort"] = reasoning_effort

        # zai-glm-4.7 supports parallel tool calls.
        if has_tools and model in _PARALLEL_TOOL_CALL_MODELS:
            extra["parallel_tool_calls"] = llm_config.get("parallel_tool_calls", True)

        return extra

    # ── Rate-limit retry ─────────────────────────────────────────

    @staticmethod
    async def _call_with_retry(fn, **kwargs) -> Any:
        """Call *fn* with exponential backoff on 429 RateLimitError.

        Retries up to ``_MAX_RETRIES`` times. Respects the ``Retry-After``
        header from the Cerebras API when available, otherwise uses
        exponential backoff starting at ``_BASE_DELAY_S``.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await fn(**kwargs)
            except RateLimitError as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break

                # Prefer Retry-After header if present
                retry_after = None
                if hasattr(exc, "response") and exc.response is not None:
                    retry_after = exc.response.headers.get("retry-after")

                if retry_after is not None:
                    delay = min(float(retry_after), _MAX_DELAY_S)
                else:
                    delay = min(_BASE_DELAY_S * (2**attempt), _MAX_DELAY_S)

                logger.warning(
                    "Cerebras 429 rate limit — attempt %d/%d, retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        raise last_exc  # type: ignore[misc]

    # ── Inference overrides ──────────────────────────────────────

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> LLMResponse:
        """Execute inference with Cerebras API.

        Delegates most logic to ``OpenAIAdapter.run_inference`` after
        injecting Cerebras-specific parameters into the request.
        """
        client = self.get_client()

        # Transform messages and tools to OpenAI-compatible format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)

        logger.info(
            f"Cerebras inference: model={model}, "
            f"messages={len(vendor_messages)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        try:
            request_params: Dict[str, Any] = {
                "model": model,
                "messages": vendor_messages,
            }
            request_params.update(
                configured_generation_params(
                    llm_config,
                    max_tokens_parameter="max_completion_tokens",
                    stop_sequences_parameter="stop",
                )
            )

            # Add tools if available
            if vendor_tools:
                request_params["tools"] = vendor_tools
                request_params["tool_choice"] = "auto"

            # Add Cerebras-specific parameters
            request_params.update(
                self._build_cerebras_params(
                    model, llm_config, has_tools=bool(vendor_tools)
                )
            )

            response = await self._call_with_retry(
                client.chat.completions.create, **request_params
            )

            # Transform to platform format — reuse OpenAI's transformer
            platform_response = self.transform_response_to_platform(response)

            # Enrich metadata with Cerebras time_info if present
            time_info = getattr(response, "time_info", None)
            if time_info is not None:
                platform_response.metadata["time_info"] = {
                    "queue_time": getattr(time_info, "queue_time", None),
                    "prompt_time": getattr(time_info, "prompt_time", None),
                    "completion_time": getattr(time_info, "completion_time", None),
                    "total_time": getattr(time_info, "total_time", None),
                }

            platform_response.metadata["vendor"] = "cerebras"
            return platform_response

        except Exception as error:
            logger.error(
                "Cerebras API request failed error_type=%s",
                type(error).__name__,
            )
            raise

    async def run_streaming_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[LLMResponse]:
        """Execute streaming inference with Cerebras API.

        Overrides the parent to inject Cerebras-specific parameters and
        to set the ``vendor`` metadata key to ``"cerebras"``.
        """
        client = self.get_client()

        # Transform messages and tools to OpenAI-compatible format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)

        logger.debug(
            f"Cerebras streaming inference: model={model}, "
            f"messages={len(vendor_messages)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        request_params: Dict[str, Any] = {
            "model": model,
            "messages": vendor_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        request_params.update(
            configured_generation_params(
                llm_config,
                max_tokens_parameter="max_completion_tokens",
                stop_sequences_parameter="stop",
            )
        )

        if vendor_tools:
            request_params["tools"] = vendor_tools
            request_params["tool_choice"] = "auto"

        # Add Cerebras-specific parameters
        request_params.update(
            self._build_cerebras_params(model, llm_config, has_tools=bool(vendor_tools))
        )

        # Reuse the OpenAI streaming accumulation logic.
        # We duplicate the streaming loop here (rather than calling super)
        # because the parent's get_client() returns AsyncOpenAI, not
        # AsyncCerebras. The streaming chunk format is identical.
        import json

        from eylo.sockets.llm.schemas import (
            LLMContentBlock,
            LLMContentType,
            LLMTextBlock,
            LLMToolUseBlock,
        )

        message_id = None
        message_model = model
        text_content = ""
        tool_calls_dict: Dict[int, Dict[str, Any]] = {}
        finish_reason = None
        usage_info = None

        try:
            stream_resp = await self._call_with_retry(
                client.chat.completions.create, **request_params
            )

            async for chunk in stream_resp:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage_info = self._normalize_usage(chunk_usage)

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if chunk.id and not message_id:
                    message_id = chunk.id
                    message_model = chunk.model

                # Handle text content deltas
                if delta.content:
                    text_content += delta.content

                    content_blocks = []
                    if text_content:
                        content_blocks.append(
                            LLMContentBlock(
                                type=LLMContentType.TEXT,
                                content=LLMTextBlock(text=text_content),
                            )
                        )

                    yield LLMResponse(
                        id=message_id or "",
                        model=message_model,
                        content=content_blocks,
                        stop_reason=None,
                        usage=usage_info,
                        role="assistant",
                        metadata={
                            "vendor": "cerebras",
                            "streaming": True,
                            "delta": {
                                "type": "text_delta",
                                "text": delta.content,
                            },
                        },
                    )

                # Handle tool call deltas
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        index = tool_call_delta.index

                        if index not in tool_calls_dict:
                            tool_calls_dict[index] = {
                                "id": getattr(tool_call_delta, "id", "") or "",
                                "name": "",
                                "arguments": "",
                            }

                        tc = tool_calls_dict[index]
                        if tool_call_delta.id:
                            tc["id"] = tool_call_delta.id
                        if (
                            hasattr(tool_call_delta, "function")
                            and tool_call_delta.function
                        ):
                            if tool_call_delta.function.name:
                                tc["name"] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                tc["arguments"] += tool_call_delta.function.arguments

                # Capture finish reason
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            # Build final response with all accumulated content
            content_blocks = []
            if text_content:
                content_blocks.append(
                    LLMContentBlock(
                        type=LLMContentType.TEXT,
                        content=LLMTextBlock(text=text_content),
                    )
                )

            for _idx, tc in sorted(tool_calls_dict.items()):
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                content_blocks.append(
                    LLMContentBlock(
                        type=LLMContentType.TOOL_USE,
                        content=LLMToolUseBlock(
                            id=tc["id"],
                            name=tc["name"],
                            input=args,
                        ),
                        id=tc["id"],
                    )
                )

            stop_reason = self._map_finish_reason(finish_reason or "stop")

            yield LLMResponse(
                id=message_id or "",
                model=message_model,
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage_info,
                role="assistant",
                metadata={
                    "vendor": "cerebras",
                    "streaming": True,
                    "final": True,
                },
            )

        except Exception as error:
            logger.error(
                "Cerebras streaming request failed error_type=%s",
                type(error).__name__,
            )
            raise
