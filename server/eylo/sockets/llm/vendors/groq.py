"""Groq vendor adapter implementation.

Groq provides an OpenAI-compatible Chat Completions API
(``https://api.groq.com/openai/v1/chat/completions``) with identical message
format, tool calling format, and response structure.  This adapter therefore
extends ``OpenAIAdapter`` and overrides only what differs:

1. **Client** — ``AsyncGroq`` instead of ``AsyncOpenAI``.
2. **Inference parameters** — Groq-specific flags per model:
   - ``include_reasoning=False`` for GPT-OSS models (skip reasoning in agentic mode).
   - ``reasoning_effort="none"`` for ``qwen/qwen3-32b`` (disable reasoning entirely).
3. **Response metadata** — Sets ``vendor: "groq"`` in ``LLMResponse.metadata``.

References:
- Groq Docs: https://console.groq.com/docs/overview
- Chat Completions: https://console.groq.com/docs/text-chat
- Tool Use: https://console.groq.com/docs/tool-use/overview
- Reasoning: https://console.groq.com/docs/reasoning
- Models: https://console.groq.com/docs/models

"""

import logging
from typing import Any, AsyncIterator, Dict, List

from groq import AsyncGroq

from eylo.common.contracts.messages import MessageInDb
from eylo.common.contracts.tool_platform import PlatformTool
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.llm.config import configured_generation_params, require_model
from eylo.sockets.llm.schemas import LLMResponse
from eylo.sockets.llm.vendors.openai import OpenAIAdapter

logger = logging.getLogger(__name__)

# GPT-OSS models support ``include_reasoning`` and ``reasoning_effort``.
_GPT_OSS_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}

# Models that support ``reasoning_effort`` with "none"/"default" semantics.
_QWEN_REASONING_MODELS = {"qwen/qwen3-32b"}


class GroqAdapter(OpenAIAdapter):
    """Groq adapter using the OpenAI-compatible API.

    Since Groq exposes an OpenAI-compatible Chat Completions endpoint,
    this adapter extends ``OpenAIAdapter`` and overrides only the client
    constructor and inference methods to inject Groq-specific parameters.

    Inherited from OpenAIAdapter (unchanged):
    - ``transform_messages_to_vendor()``
    - ``transform_response_to_platform()``
    - Message transition handlers
    - Streaming chunk accumulation
    """

    vendor_name = "groq"

    def get_client(self) -> AsyncGroq:
        """Get authenticated Groq client."""
        return AsyncGroq(api_key=self._api_key)

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform tools for Groq — standard JSON Schema without OpenAI strict mode.

        Groq does not support OpenAI's ``strict`` parameter and validates
        tool-call arguments against the schema as-is.  OpenAI strict mode
        forces *all* properties into ``required``, which causes Groq to
        reject tool calls that omit optional fields.

        This override builds tool definitions directly from the platform
        schema, adding only ``additionalProperties: false`` (which Groq
        accepts) while preserving the original ``required`` list.
        """
        vendor_tools: List[Dict[str, Any]] = []

        for tool in tools:
            if not tool.llm_config:
                logger.warning(f"Tool {tool.id} has no llm_config, skipping")
                continue

            platform_tool = tool.llm_config
            if not isinstance(platform_tool, PlatformTool):
                logger.error(
                    f"Unexpected llm_config type for tool {tool.id}: "
                    f"{type(tool.llm_config)}"
                )
                continue

            input_schema = platform_tool.input_schema.to_json_schema()
            input_schema.setdefault("properties", {})
            input_schema["additionalProperties"] = False

            vendor_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": platform_tool.name,
                        "description": platform_tool.description,
                        "parameters": input_schema,
                    },
                }
            )

        return vendor_tools

    # ── Groq-specific request parameter helpers ──────────────────

    def _build_groq_params(
        self,
        model: str,
        llm_config: Dict[str, Any],
        has_tools: bool,
    ) -> Dict[str, Any]:
        """Build Groq-specific parameters that extend the base request.

        Args:
            model: The model identifier (e.g. ``openai/gpt-oss-120b``).
            llm_config: Agent's LLM configuration dict.
            has_tools: Whether tools are included in the request.

        Returns:
            Dict of extra keyword arguments to pass to the API call.

        """
        extra: Dict[str, Any] = {}

        # GPT-OSS models: disable reasoning output for agentic workflows.
        if model in _GPT_OSS_MODELS:
            extra["include_reasoning"] = llm_config.get("include_reasoning", False)

        # Qwen3-32B: disable reasoning entirely for agentic workflows.
        if model in _QWEN_REASONING_MODELS:
            extra["reasoning_effort"] = llm_config.get("reasoning_effort", "none")

        return extra

    # ── Inference overrides ──────────────────────────────────────

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> LLMResponse:
        """Execute inference with Groq API."""
        client = self.get_client()

        # Transform messages and tools to OpenAI-compatible format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)

        logger.info(
            f"Groq inference: model={model}, "
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

            # Add Groq-specific parameters
            request_params.update(
                self._build_groq_params(model, llm_config, has_tools=bool(vendor_tools))
            )

            response = await client.chat.completions.create(**request_params)

            # Transform to platform format — reuse OpenAI's transformer
            platform_response = self.transform_response_to_platform(response)
            platform_response.metadata["vendor"] = "groq"
            return platform_response

        except Exception as error:
            logger.error(
                "Groq API request failed error_type=%s",
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
        """Execute streaming inference with Groq API."""
        client = self.get_client()

        # Transform messages and tools to OpenAI-compatible format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)

        logger.debug(
            f"Groq streaming inference: model={model}, "
            f"messages={len(vendor_messages)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        request_params: Dict[str, Any] = {
            "model": model,
            "messages": vendor_messages,
            "stream": True,
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

        # Add Groq-specific parameters
        request_params.update(
            self._build_groq_params(model, llm_config, has_tools=bool(vendor_tools))
        )

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
            stream_resp = await client.chat.completions.create(**request_params)

            async for chunk in stream_resp:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is None:
                    chunk_usage = getattr(getattr(chunk, "x_groq", None), "usage", None)
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
                            "vendor": "groq",
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
                    "vendor": "groq",
                    "streaming": True,
                    "final": True,
                },
            )

        except Exception as error:
            logger.error(
                "Groq streaming request failed error_type=%s",
                type(error).__name__,
            )
            raise
