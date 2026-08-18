"""OpenAI adapter for the `llm` socket."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Tuple
from uuid import UUID

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

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


class OpenAIAdapter(LLMVendorAdapter):
    """OpenAI/GPT LLM vendor adapter.

    Encapsulates all OpenAI-specific logic for message transformation,
    tool formatting, and response parsing.

    Key Differences from Anthropic:
    - System prompt is a message with role="system" (not separate parameter)
    - Tool calls are in message.tool_calls array
    - Tool results are messages with role="tool"
    - Response structure uses choices[0].message
    """

    vendor_name = "openai"
    max_tokens_parameter = "max_completion_tokens"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_client(self) -> AsyncOpenAI:
        """Get authenticated OpenAI client."""
        return create_openai_client(self._api_key)

    @staticmethod
    def _normalize_usage(usage: Any | None) -> LLMUsageInfo | None:
        """Normalize OpenAI-compatible token usage into the platform contract."""
        if usage is None:
            return None
        return LLMUsageInfo(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cache_read_input_tokens=getattr(
                getattr(usage, "prompt_tokens_details", None),
                "cached_tokens",
                None,
            ),
            reasoning_tokens=getattr(
                getattr(usage, "completion_tokens_details", None),
                "reasoning_tokens",
                None,
            ),
        )

    def _handle_user_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        logger.debug(
            f"[OpenAIAdapter] Handling USER message transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.USER:
            # Anthropic: merge consecutive USER messages
            logger.debug("Merging consecutive USER messages")
            prev_ = stack[-1]
            prev_.content = UserMessageContent(
                content=f"{prev_.content.get_text_content()}\n{msg.get_text_content()}"
            )
            # Keep the first user message, log the merge
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

    def transform_messages_to_vendor(
        self, messages: List[MessageInDb], system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transform Eylo messages to OpenAI format.

        OpenAI expects:
        - Messages with role: "system" | "user" | "assistant" | "tool"
        - System message should be first in the array
        - Content can be string or list of content blocks
        - Tool calls are in message.tool_calls array
        - Tool results are separate messages with role="tool"

        Returns:
            Tuple of (system_prompt, vendor_messages)
            Note: system_prompt is returned for consistency with base class,
                  but OpenAI includes it in the messages array.

        """
        # Validate message sequence
        messages = self._validate_message_sequence(messages)

        # Use typed list internally for better type checking
        vendor_messages: List[ChatCompletionMessageParam] = []

        # Add system message first if we have a system prompt
        if system_prompt:
            vendor_messages.append({"role": "system", "content": system_prompt})  # type: ignore

        for msg in messages:
            if msg.kind == MessageKind.USER:
                # User messages
                content = self._format_user_content(msg.content)
                vendor_messages.append({"role": "user", "content": content})  # type: ignore

            elif msg.kind == MessageKind.ASSISTANT:
                # Assistant messages (text responses)
                content = self._format_assistant_content(msg.content)
                vendor_messages.append({"role": "assistant", "content": content})  # type: ignore

            elif msg.kind == MessageKind.TOOL_USE:
                # Tool use messages - OpenAI puts these as assistant messages with tool_calls
                tool_calls = self._format_tool_use_content(msg.content)
                vendor_messages.append(
                    {"role": "assistant", "content": None, "tool_calls": tool_calls}  # type: ignore
                )

            elif msg.kind == MessageKind.TOOL_RESULT:
                # Tool result messages - OpenAI uses role="tool"
                tool_result_messages = self._format_tool_result_content(msg.content)
                vendor_messages.extend(tool_result_messages)

        # Cast to base class return type (List[Dict[str, Any]])
        # This is safe because ChatCompletionMessageParam is a dict at runtime
        return (system_prompt, vendor_messages)  # type: ignore

    def _format_user_content(self, content: Any) -> Any:
        """Format one typed user message for OpenAI."""
        from eylo.common.contracts.message_content import (
            UserMessageContent,
            WidgetResponseMessageContent,
            content_block_to_platform_dict,
        )

        if isinstance(content, UserMessageContent):
            return [content_block_to_platform_dict(block) for block in content.content]
        if isinstance(content, WidgetResponseMessageContent):
            return content.get_text_content()
        raise TypeError(
            f"Unsupported typed user content: {type(content).__name__}"
        )

    def _format_assistant_content(self, content: Any) -> Any:
        """Format assistant message content for OpenAI.

        Handles:
        - AssistantMessageContent: {"role": "assistant", "content": TextContent | dict}
        - ToolUseMessageContent: {"role": "tool_use", "content": ToolUseContent}
        """
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

    def _format_tool_use_content(self, content: Any) -> List[Dict[str, Any]]:
        """Format tool use content for OpenAI.

        OpenAI tool calls format:
        [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "Paris"}'
                }
            }
        ]

        """
        from eylo.common.contracts.message_content import ToolUseMessageContent

        if not isinstance(content, ToolUseMessageContent):
            raise TypeError(
                f"Unsupported typed tool-use content: {type(content).__name__}"
            )
        tool_use = content.content
        return [
            {
                "id": tool_use.id,
                "type": "function",
                "function": {
                    "name": tool_use.name,
                    "arguments": json.dumps(tool_use.input),
                },
            }
        ]

    def _format_tool_result_content(
        self, content: Any
    ) -> List[ChatCompletionMessageParam]:
        """Format tool result content for OpenAI.

        OpenAI tool result format:
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": "The weather in Paris is 72°F"
        }
        """
        from eylo.common.contracts.message_content import ToolResultMessageContent

        if not isinstance(content, ToolResultMessageContent):
            raise TypeError(
                f"Unsupported typed tool-result content: {type(content).__name__}"
            )
        return [
            {
                "role": "tool",
                "tool_call_id": result.tool_use_id,
                "content": serialize_tool_content(result.content),
            }  # type: ignore
            for result in content.content
        ]

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform platform-native tools to OpenAI Chat Completions format.

        Delegates extraction to ``extract_openai_function_declarations``
        and wraps each declaration in the nested
        ``{"type": "function", "function": {..., "strict": True}}``
        structure required by the Chat Completions API.
        """
        declarations = extract_openai_function_declarations(tools)
        vendor_tools: List[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {
                    **d,
                    "strict": True,
                },
            }
            for d in declarations
        ]
        return vendor_tools  # type: ignore

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> LLMResponse:
        """Execute inference with OpenAI API.

        Args:
            messages: Platform-native message history
            system_prompt: System instructions for the model
            tools: Available tools for the model
            llm_config: Model configuration (model name, temperature, etc.)
            stream: Whether to stream the response (not implemented yet)

        Returns:
            LLMResponse: Standardized platform response

        """
        client = self.get_client()

        # Transform messages and tools to OpenAI format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)
        logger.info(
            f"OpenAI inference: model={model}, messages={len(vendor_messages)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        try:
            # Build request parameters
            request_params: Dict[str, Any] = {
                "model": model,
                "messages": vendor_messages,
            }
            request_params.update(
                configured_generation_params(
                    llm_config,
                    max_tokens_parameter=self.max_tokens_parameter,
                    stop_sequences_parameter="stop",
                )
            )

            # Add tools if available
            if vendor_tools:
                request_params["tools"] = vendor_tools
                # Allow the model to decide whether to use tools
                request_params["tool_choice"] = "auto"

            # Make API call
            response: ChatCompletion = await client.chat.completions.create(
                **request_params
            )

            # Transform response to platform format
            return self.transform_response_to_platform(response)

        except Exception as error:
            logger.error(
                "OpenAI API request failed error_type=%s",
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
        """Execute streaming inference with OpenAI API."""
        client = self.get_client()

        # Transform messages and tools to OpenAI format
        _, vendor_messages = self.transform_messages_to_vendor(messages, system_prompt)
        vendor_tools = self.transform_tools_to_vendor(tools) if tools else None

        # Extract model config
        model = require_model(llm_config)
        logger.debug(
            f"OpenAI streaming inference: model={model}, messages={len(vendor_messages)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        # Build request parameters
        request_params = {
            "model": model,
            "messages": vendor_messages,
            "stream": True,
        }
        if self.vendor_name == "openai":
            request_params["stream_options"] = {"include_usage": True}

        request_params.update(
            configured_generation_params(
                llm_config,
                max_tokens_parameter=self.max_tokens_parameter,
                stop_sequences_parameter="stop",
            )
        )

        # Add tools if available
        if vendor_tools:
            request_params["tools"] = vendor_tools
            request_params["tool_choice"] = "auto"

        # Accumulate state for building complete response
        message_id = None
        message_model = model
        text_content = ""
        tool_calls_dict: Dict[int, Dict[str, Any]] = {}  # Keyed by index
        finish_reason = None
        usage_info = None

        try:
            # Create streaming request
            stream = await client.chat.completions.create(**request_params)

            async for chunk in stream:
                # OpenAI reports aggregate usage in a final chunk whose choices
                # list is empty. Capture it before the ordinary delta guard.
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage:
                    usage_info = self._normalize_usage(chunk_usage)

                # Extract chunk data
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Capture message ID from first chunk
                if chunk.id and not message_id:
                    message_id = chunk.id
                    message_model = chunk.model

                # Handle text content deltas
                if delta.content:
                    text_content += delta.content

                    # Build content blocks for current state
                    content_blocks = []
                    if text_content:
                        content_blocks.append(
                            LLMContentBlock(
                                type=LLMContentType.TEXT,
                                content=LLMTextBlock(text=text_content),
                            )
                        )

                    # Yield partial response with text delta
                    yield LLMResponse(
                        id=message_id or "",
                        model=message_model,
                        content=content_blocks,
                        stop_reason=None,
                        usage=usage_info,
                        role="assistant",
                        metadata={
                            "vendor": self.vendor_name,
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

                        # Initialize tool call if new
                        if index not in tool_calls_dict:
                            tool_calls_dict[index] = {
                                "id": tool_call_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        # Update tool call data
                        if tool_call_delta.id:
                            tool_calls_dict[index]["id"] = tool_call_delta.id

                        if tool_call_delta.function and tool_call_delta.function.name:
                            tool_calls_dict[index]["name"] = (
                                tool_call_delta.function.name
                            )

                        if (
                            tool_call_delta.function
                            and tool_call_delta.function.arguments
                        ):
                            # Accumulate arguments
                            tool_calls_dict[index]["arguments"] += (
                                tool_call_delta.function.arguments
                            )

                # Handle finish reason
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            # After stream completes, build final response
            content_blocks = []

            # Add text content if present
            if text_content:
                content_blocks.append(
                    LLMContentBlock(
                        type=LLMContentType.TEXT,
                        content=LLMTextBlock(text=text_content),
                    )
                )

            # Add completed tool calls
            for index in sorted(tool_calls_dict.keys()):
                tool_call = tool_calls_dict[index]
                try:
                    # Parse accumulated JSON arguments
                    arguments = (
                        json.loads(tool_call["arguments"])
                        if tool_call["arguments"]
                        else {}
                    )

                    content_blocks.append(
                        LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=tool_call["id"],
                                name=tool_call["name"],
                                input=arguments,
                            ),
                            id=tool_call["id"],
                        )
                    )

                    # Yield tool call completion
                    yield LLMResponse(
                        id=message_id or "",
                        model=message_model,
                        content=content_blocks,
                        stop_reason=None,
                        usage=usage_info,
                        role="assistant",
                        metadata={
                            "vendor": self.vendor_name,
                            "streaming": True,
                            "delta": {
                                "type": "tool_call_complete",
                                "index": index,
                                "tool_id": tool_call["id"],
                                "tool_name": tool_call["name"],
                                "tool_input": arguments,
                            },
                        },
                    )

                except json.JSONDecodeError as error:
                    logger.error(
                        "Failed to parse streamed tool input index=%d error_type=%s",
                        index,
                        type(error).__name__,
                    )

            # Map finish reason
            stop_reason = (
                self._map_finish_reason(finish_reason) if finish_reason else None
            )

            # Yield final complete response
            final_response = LLMResponse(
                id=message_id or "",
                model=message_model,
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage_info,
                role="assistant",
                metadata={
                    "vendor": self.vendor_name,
                    "streaming": False,
                    "finish_reason": finish_reason,
                },
            )
            yield final_response
            return

        except Exception as error:
            logger.error(
                "OpenAI streaming request failed error_type=%s",
                type(error).__name__,
            )
            raise

    def transform_response_to_platform(
        self, vendor_response: ChatCompletion
    ) -> LLMResponse:
        """Transform OpenAI response to platform-native LLMResponse.

        OpenAI response structure:
        {
            "id": "chatcmpl-abc123",
            "model": "gpt-4o",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "text response",
                    "tool_calls": [...]
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        """
        try:
            # Extract first choice (OpenAI typically returns single choice)
            choice = vendor_response.choices[0]
            message = choice.message

            # Build content blocks
            content_blocks: List[LLMContentBlock] = []

            # Add text content if present
            if message.content:
                content_blocks.append(
                    LLMContentBlock(
                        type=LLMContentType.TEXT,
                        content=LLMTextBlock(text=message.content),
                    )
                )

            # Add tool calls if present
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    # Type guard: OpenAI tool calls can be function calls or custom tools
                    # We only handle function calls here
                    if hasattr(tool_call, "function"):
                        content_blocks.append(
                            LLMContentBlock(
                                type=LLMContentType.TOOL_USE,
                                content=LLMToolUseBlock(
                                    id=tool_call.id,
                                    name=tool_call.function.name,  # type: ignore
                                    input=json.loads(tool_call.function.arguments),  # type: ignore
                                ),
                                id=tool_call.id,
                            )
                        )

            # Extract usage info
            usage = self._normalize_usage(vendor_response.usage)

            # Map finish reason
            stop_reason = self._map_finish_reason(choice.finish_reason)

            return LLMResponse(
                id=vendor_response.id,
                model=vendor_response.model,
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage,
                role="assistant",
                metadata={
                    "vendor": self.vendor_name,
                    "finish_reason": choice.finish_reason,
                    "system_fingerprint": vendor_response.system_fingerprint,
                },
            )

        except Exception as error:
            logger.error(
                "OpenAI response transformation failed error_type=%s",
                type(error).__name__,
            )
            raise

    def _map_finish_reason(self, openai_reason: str) -> str:
        """Map OpenAI finish reasons to platform stop reasons.

        OpenAI finish reasons:
        - "stop": Natural stop point
        - "length": Max tokens reached
        - "tool_calls": Model called tools
        - "content_filter": Content filtered
        - "function_call": (deprecated) Function called
        """
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "function_call": "tool_use",  # Legacy
            "content_filter": "content_filter",
        }
        return mapping.get(openai_reason, openai_reason)
