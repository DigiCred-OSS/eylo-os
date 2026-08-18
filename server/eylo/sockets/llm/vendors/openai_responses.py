"""OpenAI Responses adapter for the `llm` socket."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import UUID

from openai import AsyncOpenAI

from eylo.common.contracts.message_content import UserMessageContent
from eylo.common.contracts.messages import (
    MessageInDb,
    MessageKind,
)
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.llm.base import LLMVendorAdapter
from eylo.sockets.llm.config import configured_generation_params, require_model
from eylo.sockets.llm.schemas import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
    LLMUsageInfo,
)
from eylo.sockets.llm.vendors.openai_utils import (
    create_openai_client,
    extract_openai_function_declarations,
    serialize_tool_content,
)

logger = logging.getLogger(__name__)


class OpenAIResponsesAdapter(LLMVendorAdapter):
    """OpenAI Responses API vendor adapter.

    Uses the Responses API (client.responses.create) which provides:
    - Separate `instructions` parameter for system prompts
    - `input` parameter accepting strings or structured item arrays
    - Output as a list of typed items (messages, function_calls)
    - Event-based streaming with typed event objects

    Key Differences from OpenAIAdapter (Chat Completions):
    - System prompt → `instructions` param (not a message in the array)
    - Messages → `input` items with content type wrappers
    - Tool calls → `function_call` output items with `call_id`
    - Tool results → `function_call_output` input items
    - Response → `output` item array (not choices[0].message)
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_client(self) -> AsyncOpenAI:
        """Get authenticated OpenAI client."""
        return create_openai_client(self._api_key)

    # ── Message transition overrides ──────────────────────────────
    # The Responses API is more lenient with message ordering since
    # it uses structured input items rather than strict role sequences.
    # We reuse the base class validation which handles the state machine.

    def _handle_user_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        logger.debug(
            f"[OpenAIResponsesAdapter] Handling USER transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.USER:
            # Merge consecutive USER messages
            prev_ = stack[-1]
            prev_.content = UserMessageContent(
                content=f"{prev_.content.get_text_content()}\n{msg.get_text_content()}"
            )
            stack[-1] = prev_
        elif current_kind == MessageKind.ASSISTANT:
            stack.append(msg)
        elif current_kind == MessageKind.TOOL_USE:
            tool_id = self._extract_tool_use_id(msg)
            if not tool_id:
                logger.error(
                    f"TOOL_USE message missing 'id' field. Rejecting message {msg.id}"
                )
                return
            pending_tool_calls[tool_id] = msg.id
            stack.append(msg)
        else:
            logger.warning(
                f"Invalid transition: USER -> {current_kind}. Skipping message."
            )

    # ── Message transformation ────────────────────────────────────

    def transform_messages_to_vendor(
        self, messages: List[MessageInDb], system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transform Eylo messages to Responses API input items format.

        Responses API expects:
        - `instructions` parameter for system prompt (returned as first tuple element)
        - `input` array of items, each with role and typed content blocks:
            - User: {"role": "user", "content": [{"type": "input_text", "text": "..."}]}
            - Assistant: {"role": "assistant", "content": [{"type": "output_text", "text": "..."}]}
            - Tool calls: {"type": "function_call", "call_id": "...", "name": "...", "arguments": "..."}
            - Tool results: {"type": "function_call_output", "call_id": "...", "output": "..."}

        Returns:
            Tuple of (instructions, input_items)

        """
        messages = self._validate_message_sequence(messages)

        input_items: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.kind == MessageKind.USER:
                input_items.append(
                    {
                        "role": "user",
                        "content": self._format_user_content(msg.content),
                    }
                )

            elif msg.kind == MessageKind.ASSISTANT:
                content = self._format_assistant_content(msg.content)
                if content:
                    input_items.append(
                        {
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": content}],
                        }
                    )

            elif msg.kind == MessageKind.TOOL_USE:
                # Responses API: tool calls are top-level function_call items
                tool_calls = self._format_tool_use_as_function_calls(msg.content)
                input_items.extend(tool_calls)

            elif msg.kind == MessageKind.TOOL_RESULT:
                # Responses API: tool results are function_call_output items
                tool_outputs = self._format_tool_result_as_outputs(msg.content)
                input_items.extend(tool_outputs)

        return (system_prompt, input_items)

    def _format_user_content(self, content: Any) -> List[Dict[str, Any]]:
        """Format user content as Responses API input blocks."""
        from eylo.common.contracts.message_content import (
            UserMessageContent,
            WidgetResponseMessageContent,
        )

        if isinstance(content, UserMessageContent):
            return [self._format_user_content_block(block) for block in content.content]
        if isinstance(content, WidgetResponseMessageContent):
            return [{"type": "input_text", "text": content.get_text_content()}]
        raise TypeError(
            f"Unsupported typed user content: {type(content).__name__}"
        )

    def _format_user_content_block(self, block: Any) -> Dict[str, Any]:
        from eylo.common.contracts.message_content import (
            ImageUrlContent,
            TextContent,
        )

        if isinstance(block, TextContent):
            return {"type": "input_text", "text": block.text}
        if isinstance(block, ImageUrlContent):
            return {"type": "input_image", "image_url": block.image_url.url}
        raise TypeError(
            f"Unsupported typed user content block: {type(block).__name__}"
        )

    def _format_assistant_content(self, content: Any) -> Optional[str]:
        """Extract text string from assistant message content."""
        from eylo.common.contracts.message_content import (
            AssistantMessageContent,
            WidgetMessageContent,
        )

        if isinstance(content, AssistantMessageContent):
            return content.get_text_content()

        if isinstance(content, WidgetMessageContent):
            return content.get_text_content()
        raise TypeError(
            f"Unsupported typed assistant content: {type(content).__name__}"
        )

    def _format_tool_use_as_function_calls(self, content: Any) -> List[Dict[str, Any]]:
        """Format tool use content as Responses API function_call items.

        Responses API format:
        {
            "type": "function_call",
            "call_id": "call_abc123",
            "name": "get_weather",
            "arguments": '{"location": "Paris"}'
        }
        """
        from eylo.common.contracts.message_content import ToolUseMessageContent

        if not isinstance(content, ToolUseMessageContent):
            raise TypeError(
                f"Unsupported typed tool-use content: {type(content).__name__}"
            )
        tool_use = content.content
        return [
            {
                "type": "function_call",
                "call_id": tool_use.id,
                "name": tool_use.name,
                "arguments": json.dumps(tool_use.input),
            }
        ]

    def _format_tool_result_as_outputs(self, content: Any) -> List[Dict[str, Any]]:
        """Format tool result content as Responses API function_call_output items.

        Responses API format:
        {
            "type": "function_call_output",
            "call_id": "call_abc123",
            "output": "The weather in Paris is 72°F"
        }
        """
        from eylo.common.contracts.message_content import ToolResultMessageContent

        if not isinstance(content, ToolResultMessageContent):
            raise TypeError(
                f"Unsupported typed tool-result content: {type(content).__name__}"
            )
        return [
            {
                "type": "function_call_output",
                "call_id": result.tool_use_id,
                "output": serialize_tool_content(result.content),
            }
            for result in content.content
        ]

    # ── Tool transformation ───────────────────────────────────────

    @staticmethod
    def _handle_output_item_added(
        function_calls: Dict[str, Dict[str, Any]],
        item: Any,
    ) -> Optional[str]:
        """Process a ``response.output_item.added`` event for function calls.

        Returns the call_id if the item is a function_call, else None.
        """
        if not item or getattr(item, "type", None) != "function_call":
            return None

        call_id = getattr(item, "call_id", None) or getattr(item, "id", None)
        name = getattr(item, "name", "")
        if not call_id:
            return None

        if call_id not in function_calls:
            function_calls[call_id] = {
                "call_id": call_id,
                "name": name,
                "arguments": "",
            }
        elif name:
            function_calls[call_id]["name"] = name

        return call_id

    @staticmethod
    def _reconcile_function_call_from_item(
        function_calls: Dict[str, Dict[str, Any]],
        item: Any,
    ) -> None:
        """Reconcile a completed function_call output item with accumulated state.

        The Responses API uses two IDs per function call: ``item.id`` (fc_ prefix)
        and ``item.call_id`` (call_ prefix).  Streaming delta events may key by
        either, so ``output_item.done`` is the definitive source of truth that
        lets us backfill missing names caused by key mismatches.
        """
        item_call_id = getattr(item, "call_id", None)
        item_id = getattr(item, "id", None)
        name = getattr(item, "name", "") or ""
        arguments = getattr(item, "arguments", "") or ""

        fc_entry = function_calls.get(item_call_id) or function_calls.get(item_id)

        if fc_entry:
            if name and not fc_entry["name"]:
                fc_entry["name"] = name
            if item_call_id:
                fc_entry["call_id"] = item_call_id
        elif item_call_id or item_id:
            key = item_call_id or item_id
            function_calls[key] = {
                "call_id": item_call_id or item_id,
                "name": name,
                "arguments": arguments,
            }

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform platform-native tools to Responses API format.

        Delegates extraction to ``extract_openai_function_declarations``
        and wraps each declaration in the flat
        ``{"type": "function", "name", "description", "parameters", "strict": True}``
        structure required by the Responses API (unlike Chat Completions,
        the Responses API puts fields at the top level, not under ``function``).
        """
        declarations = extract_openai_function_declarations(tools)
        return [{"type": "function", **d, "strict": True} for d in declarations]

    # ── Tool result formatting ────────────────────────────────────

    # ── Inference ─────────────────────────────────────────────────

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> LLMResponse:
        """Execute inference with OpenAI Responses API.

        Uses client.responses.create() with:
        - `instructions` for system prompt
        - `input` for conversation items
        - `tools` for function definitions
        """
        client = self.get_client()

        instructions, input_items = self.transform_messages_to_vendor(
            messages, system_prompt
        )
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        model = require_model(llm_config)

        logger.info(
            f"OpenAI Responses inference: model={model}, input_items={len(input_items)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        try:
            request_params: Dict[str, Any] = {
                "model": model,
                "input": input_items,
            }

            if instructions:
                request_params["instructions"] = instructions

            request_params.update(
                configured_generation_params(
                    llm_config,
                    max_tokens_parameter="max_output_tokens",
                    stop_sequences_parameter=None,
                )
            )

            if vendor_tools:
                request_params["tools"] = vendor_tools

            response = await client.responses.create(**request_params)

            return self.transform_response_to_platform(response)

        except Exception as error:
            logger.error(
                "OpenAI Responses API request failed error_type=%s",
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
        """Execute streaming inference with OpenAI Responses API.

        Uses event-based streaming with typed events:
        - response.output_text.delta → text content delta
        - response.function_call_arguments.delta → tool call argument delta
        - response.function_call_arguments.done → tool call complete
        - response.completed → final response
        """
        client = self.get_client()

        instructions, input_items = self.transform_messages_to_vendor(
            messages, system_prompt
        )
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        model = require_model(llm_config)

        logger.debug(
            f"OpenAI Responses streaming: model={model}, input_items={len(input_items)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        request_params: Dict[str, Any] = {
            "model": model,
            "input": input_items,
            "stream": True,
        }

        if instructions:
            request_params["instructions"] = instructions

        request_params.update(
            configured_generation_params(
                llm_config,
                max_tokens_parameter="max_output_tokens",
                stop_sequences_parameter=None,
            )
        )

        if vendor_tools:
            request_params["tools"] = vendor_tools

        # Accumulate state for building complete response
        response_id: Optional[str] = None
        response_model = model
        text_content = ""
        # Track function calls by item_id or index
        function_calls: Dict[str, Dict[str, Any]] = {}
        current_function_call_id: Optional[str] = None
        finish_reason: Optional[str] = None
        usage_info: Optional[LLMUsageInfo] = None

        try:
            stream = await client.responses.create(**request_params)

            async for event in stream:
                event_type = event.type if hasattr(event, "type") else str(event)

                # Capture response ID from the response.created event
                if event_type == "response.created":
                    if hasattr(event, "response") and hasattr(event.response, "id"):
                        response_id = event.response.id
                        response_model = getattr(event.response, "model", model)

                # Handle text deltas
                elif event_type == "response.output_text.delta":
                    delta_text = getattr(event, "delta", "")
                    if delta_text:
                        text_content += delta_text

                        content_blocks = []
                        if text_content:
                            content_blocks.append(
                                LLMContentBlock(
                                    type=LLMContentType.TEXT,
                                    content=LLMTextBlock(text=text_content),
                                )
                            )

                        yield LLMResponse(
                            id=response_id or "",
                            model=response_model,
                            content=content_blocks,
                            stop_reason=None,
                            usage=usage_info,
                            role="assistant",
                            metadata={
                                "vendor": "openai_responses",
                                "streaming": True,
                                "delta": {
                                    "type": "text_delta",
                                    "text": delta_text,
                                },
                            },
                        )

                # Handle function call start
                elif event_type == "response.function_call_arguments.delta":
                    # Extract call_id from the event
                    call_id = getattr(event, "call_id", None) or getattr(
                        event, "item_id", None
                    )
                    delta_args = getattr(event, "delta", "")

                    if call_id:
                        current_function_call_id = call_id
                        if call_id not in function_calls:
                            function_calls[call_id] = {
                                "call_id": call_id,
                                "name": "",
                                "arguments": "",
                            }
                        function_calls[call_id]["arguments"] += delta_args

                # Handle function call complete
                elif event_type == "response.function_call_arguments.done":
                    call_id = getattr(event, "call_id", None) or getattr(
                        event, "item_id", current_function_call_id
                    )
                    name = getattr(event, "name", "")
                    arguments = getattr(event, "arguments", "")

                    if call_id:
                        if call_id not in function_calls:
                            function_calls[call_id] = {
                                "call_id": call_id,
                                "name": name,
                                "arguments": arguments,
                            }
                        else:
                            if name:
                                function_calls[call_id]["name"] = name
                            if arguments:
                                function_calls[call_id]["arguments"] = arguments

                # Handle output item added (captures function_call name)
                elif event_type == "response.output_item.added":
                    resolved_id = self._handle_output_item_added(
                        function_calls, getattr(event, "item", None)
                    )
                    if resolved_id:
                        current_function_call_id = resolved_id

                # Handle output item done — definitive source of truth
                # for function call name, call_id, and arguments.
                # Resolves key mismatches between item_id and call_id
                # that can leave function calls with empty names.
                elif event_type == "response.output_item.done":
                    item = getattr(event, "item", None)
                    if item and getattr(item, "type", None) == "function_call":
                        self._reconcile_function_call_from_item(function_calls, item)

                # Handle response completed
                elif event_type == "response.completed":
                    resp = getattr(event, "response", None)
                    if resp:
                        response_id = getattr(resp, "id", response_id)
                        response_model = getattr(resp, "model", response_model)
                        finish_reason = getattr(resp, "status", "completed")

                        resp_usage = getattr(resp, "usage", None)
                        if resp_usage:
                            usage_info = LLMUsageInfo(
                                input_tokens=getattr(resp_usage, "input_tokens", 0),
                                output_tokens=getattr(resp_usage, "output_tokens", 0),
                                cache_read_input_tokens=getattr(
                                    getattr(resp_usage, "input_tokens_details", None),
                                    "cached_tokens",
                                    None,
                                ),
                                reasoning_tokens=getattr(
                                    getattr(resp_usage, "output_tokens_details", None),
                                    "reasoning_tokens",
                                    None,
                                ),
                            )

            # Build final response with all content
            content_blocks = []

            if text_content:
                content_blocks.append(
                    LLMContentBlock(
                        type=LLMContentType.TEXT,
                        content=LLMTextBlock(text=text_content),
                    )
                )

            for fc in function_calls.values():
                if not fc["name"]:
                    logger.error("Skipping provider function call with empty name")
                    continue

                try:
                    arguments = json.loads(fc["arguments"]) if fc["arguments"] else {}

                    content_blocks.append(
                        LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=fc["call_id"],
                                name=fc["name"],
                                input=arguments,
                            ),
                            id=fc["call_id"],
                        )
                    )

                    # Yield tool call completion event
                    yield LLMResponse(
                        id=response_id or "",
                        model=response_model,
                        content=content_blocks,
                        stop_reason=None,
                        usage=usage_info,
                        role="assistant",
                        metadata={
                            "vendor": "openai_responses",
                            "streaming": True,
                            "delta": {
                                "type": "tool_call_complete",
                                "tool_id": fc["call_id"],
                                "tool_name": fc["name"],
                                "tool_input": arguments,
                            },
                        },
                    )

                except json.JSONDecodeError as error:
                    logger.error(
                        "Failed to parse streamed function-call input error_type=%s",
                        type(error).__name__,
                    )

            stop_reason = self._map_status_to_stop_reason(finish_reason)

            final_response = LLMResponse(
                id=response_id or "",
                model=response_model,
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage_info,
                role="assistant",
                metadata={
                    "vendor": "openai_responses",
                    "streaming": False,
                    "status": finish_reason,
                },
            )
            yield final_response
            return

        except Exception as error:
            logger.error(
                "OpenAI Responses streaming request failed error_type=%s",
                type(error).__name__,
            )
            raise

    # ── Response transformation ───────────────────────────────────

    def transform_response_to_platform(self, vendor_response: Any) -> LLMResponse:
        """Transform Responses API response to platform-native LLMResponse.

        Responses API response structure:
        {
            "id": "resp_abc123",
            "model": "gpt-4o",
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "..."}]},
                {"type": "function_call", "call_id": "...", "name": "...", "arguments": "..."}
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        }
        """
        try:
            content_blocks: List[LLMContentBlock] = []

            output = getattr(vendor_response, "output", []) or []

            for item in output:
                item_type = getattr(item, "type", None)

                if item_type == "message":
                    # Extract text from message content blocks
                    item_content = getattr(item, "content", []) or []
                    for content_item in item_content:
                        ct = getattr(content_item, "type", None)
                        if ct == "output_text":
                            text = getattr(content_item, "text", "")
                            if text:
                                content_blocks.append(
                                    LLMContentBlock(
                                        type=LLMContentType.TEXT,
                                        content=LLMTextBlock(text=text),
                                    )
                                )
                        elif ct == "refusal":
                            refusal = getattr(content_item, "refusal", "")
                            if refusal:
                                content_blocks.append(
                                    LLMContentBlock(
                                        type=LLMContentType.TEXT,
                                        content=LLMTextBlock(
                                            text=f"[Refusal] {refusal}"
                                        ),
                                    )
                                )

                elif item_type == "function_call":
                    call_id = getattr(item, "call_id", "")
                    name = getattr(item, "name", "")
                    arguments_str = getattr(item, "arguments", "{}")

                    try:
                        arguments = (
                            json.loads(arguments_str)
                            if isinstance(arguments_str, str)
                            else arguments_str or {}
                        )
                    except json.JSONDecodeError:
                        logger.error("Failed to parse function-call input")
                        arguments = {}

                    content_blocks.append(
                        LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=call_id,
                                name=name,
                                input=arguments,
                            ),
                            id=call_id,
                        )
                    )

            # Extract usage info
            usage = None
            resp_usage = getattr(vendor_response, "usage", None)
            if resp_usage:
                usage = LLMUsageInfo(
                    input_tokens=getattr(resp_usage, "input_tokens", 0),
                    output_tokens=getattr(resp_usage, "output_tokens", 0),
                    cache_read_input_tokens=getattr(
                        getattr(resp_usage, "input_tokens_details", None),
                        "cached_tokens",
                        None,
                    ),
                    reasoning_tokens=getattr(
                        getattr(resp_usage, "output_tokens_details", None),
                        "reasoning_tokens",
                        None,
                    ),
                )

            status = getattr(vendor_response, "status", "completed")
            stop_reason = self._map_status_to_stop_reason(status)

            return LLMResponse(
                id=getattr(vendor_response, "id", ""),
                model=getattr(vendor_response, "model", ""),
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage,
                role="assistant",
                metadata={
                    "vendor": "openai_responses",
                    "status": status,
                },
            )

        except Exception as error:
            logger.error(
                "OpenAI Responses API response transformation failed error_type=%s",
                type(error).__name__,
            )
            raise

    def _map_status_to_stop_reason(self, status: Optional[str]) -> Optional[str]:
        """Map Responses API status to platform stop reasons.

        Responses API statuses:
        - "completed": Normal completion
        - "incomplete": Stopped due to max tokens or other limits
        - "failed": Error occurred
        - "cancelled": Request was cancelled
        """
        if not status:
            return None
        mapping = {
            "completed": "end_turn",
            "incomplete": "max_tokens",
            "failed": "error",
            "cancelled": "cancelled",
        }
        return mapping.get(status, status)

    # ── Content block accessors ───────────────────────────────────
