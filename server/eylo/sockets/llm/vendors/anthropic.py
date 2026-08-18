"""Anthropic LLM vendor adapter implementation.

This module provides integration with Anthropic's Claude language models,
implementing the LLMVendorAdapter interface to handle all Claude-specific
message transformations, tool formatting, and response parsing.
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Tuple, Union

from anthropic import AsyncAnthropic, AsyncAnthropicBedrock
from anthropic.types import Message as ClaudeMessage
from anthropic.types import ToolParam

from eylo.common.contracts.messages import (
    MessageInDb,
    MessageKind,
)
from eylo.common.contracts.tool_platform import PlatformTool
from eylo.common.contracts.tool_record import ToolRecord
from eylo.common.utils.toon_serde import toon_encode
from eylo.sockets.llm.base import LLMVendorAdapter
from eylo.sockets.llm.config import (
    configured_generation_params,
    require_max_tokens,
    require_model,
)
from eylo.sockets.llm.schemas import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
    LLMUsageInfo,
)

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMVendorAdapter):
    """Anthropic/Claude LLM vendor adapter.

    Encapsulates all Claude-specific logic for message transformation,
    tool formatting, and response parsing.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_client(self) -> Union[AsyncAnthropic, "AsyncAnthropicBedrock"]:
        """Get authenticated Anthropic client."""
        return AsyncAnthropic(api_key=self._api_key)

    def transform_messages_to_vendor(
        self, messages: List[MessageInDb], system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transform Eylo messages to Claude format.

        Claude expects:
        - Separate system prompt
        - Messages with role: "user" | "assistant"
        - Content can be string or list of content blocks
        - Tool use and tool results as specific content block types
        """
        # Validate message sequence before transformation
        messages = self._validate_message_sequence(messages)

        vendor_messages = []

        for msg in messages:
            if msg.kind == MessageKind.USER:
                vendor_messages.append(
                    {"role": "user", "content": self._format_user_content(msg.content)}
                )

            elif msg.kind == MessageKind.ASSISTANT:
                vendor_messages.append(
                    {
                        "role": "assistant",
                        "content": self._format_assistant_content(msg.content),
                    }
                )

            elif msg.kind == MessageKind.TOOL_USE:
                # Claude represents tool use as assistant message
                # with tool_use content blocks
                try:
                    # Parse and validate content using Pydantic schema
                    parsed_msg = msg.get_tool_use_content()
                    tool_use = parsed_msg.content

                    vendor_messages.append(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": str(
                                        tool_use.id
                                    ),  # Ensure string (may be UUID)
                                    "name": tool_use.name,
                                    "input": tool_use.input,
                                }
                            ],
                        }
                    )
                except ValueError as error:
                    logger.warning(
                        "Failed to parse TOOL_USE message=%s error_type=%s",
                        msg.id,
                        type(error).__name__,
                    )
                    continue

            elif msg.kind == MessageKind.TOOL_RESULT:
                # Claude expects tool results as user messages
                # with tool_result content blocks
                try:
                    # Parse and validate content using Pydantic schema
                    parsed_msg = msg.get_tool_result_content()
                    # Get the first tool result (usually there's only one)
                    if not parsed_msg.content:
                        logger.warning(
                            f"TOOL_RESULT message {msg.id} has empty content"
                        )
                        continue

                    tool_result = parsed_msg.content[0]

                    vendor_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": str(
                                        tool_result.tool_use_id
                                    ),  # Ensure string
                                    "content": self._serialize_tool_content(
                                        tool_result.content
                                    ),
                                    "is_error": tool_result.is_error,
                                }
                            ],
                        }
                    )
                except ValueError as error:
                    logger.warning(
                        "Failed to parse TOOL_RESULT message=%s error_type=%s",
                        msg.id,
                        type(error).__name__,
                    )
                    continue

        return (system_prompt, vendor_messages)

    def _format_user_content(self, content: Any) -> Any:
        """Format one typed user message for Claude."""
        from eylo.common.contracts.message_content import (
            UserMessageContent,
            WidgetResponseMessageContent,
        )

        if isinstance(content, UserMessageContent):
            return [self._format_user_content_block(block) for block in content.content]
        if isinstance(content, WidgetResponseMessageContent):
            return content.get_text_content()
        raise TypeError(
            f"Unsupported typed user content: {type(content).__name__}"
        )

    def _format_user_content_block(self, block: Any) -> Dict[str, Any]:
        from eylo.common.contracts.message_content import (
            ImageUrlContent,
            TextContent,
        )

        if isinstance(block, TextContent):
            return {"type": "text", "text": block.text}
        if isinstance(block, ImageUrlContent):
            return {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": block.image_url.url,
                },
            }
        raise TypeError(
            f"Unsupported typed user content block: {type(block).__name__}"
        )

    def _format_assistant_content(self, content: Any) -> Any:
        """Format assistant message content for Claude.

        Converts application-native format (typed Pydantic schemas) to Claude's expected format.

        Handles:
        - AssistantMessageContent: {"role": "assistant", "content": TextContent | dict}
        - ToolUseMessageContent: {"role": "tool_use", "content": ToolUseContent}
        """
        from eylo.common.contracts.message_content import (
            AssistantMessageContent,
            WidgetMessageContent,
        )

        if isinstance(content, AssistantMessageContent):
            return [self._format_user_content_block(block) for block in content.content]
        if isinstance(content, WidgetMessageContent):
            return [{"type": "text", "text": content.get_text_content()}]
        raise TypeError(
            f"Unsupported typed assistant content: {type(content).__name__}"
        )

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform platform-native tools to Claude format.

        Converts PlatformTool -> Claude tool format:
        {
            "name": "tool_name",
            "description": "Tool description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        vendor_tools = []

        for tool in tools:
            # Tools are now stored as PlatformTool in the database
            if isinstance(tool.llm_config, PlatformTool):
                # Convert PlatformTool to Claude format (they're already compatible)
                tool_dict = ToolParam(
                    name=tool.llm_config.name,
                    description=tool.llm_config.description,
                    input_schema=tool.llm_config.input_schema.to_json_schema(),
                )
            else:
                logger.error(
                    f"Unexpected llm_config type for tool {tool.id}: {type(tool.llm_config)}"
                )
                continue

            vendor_tools.append(ToolParam(**tool_dict))

        return vendor_tools

    def _serialize_tool_content(self, content: Any) -> str:
        """Serialize tool content to string for Claude."""
        if isinstance(content, str):
            return content
        elif isinstance(content, (dict, list)):
            return toon_encode(content)
        else:
            return str(content)

    def _apply_prompt_caching(
        self,
        system_prompt: str,
        vendor_messages: List[Dict[str, Any]],
        vendor_tools: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Apply Anthropic prompt caching breakpoints."""
        # 1. System prompt as a cached content block
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # 2. Cache after the last tool definition
        cached_tools = list(vendor_tools)
        if cached_tools:
            last_tool = dict(cached_tools[-1])
            last_tool["cache_control"] = {"type": "ephemeral"}
            cached_tools[-1] = last_tool

        # 3. Conversation tail — mark the last two user-role messages.
        # Do not move this to the absolute last message: assistant/tool messages may
        # follow a user turn, and user-role tool_result messages are valid cache
        # boundaries for preserving a large stable conversation prefix.
        cached_messages = [dict(m) for m in vendor_messages]
        user_indices = [
            i for i, m in enumerate(cached_messages) if m.get("role") == "user"
        ]
        # Take the last two user message indices
        tail_indices = user_indices[-2:] if len(user_indices) >= 2 else user_indices
        for idx in tail_indices:
            msg = cached_messages[idx]
            content = msg.get("content")
            if isinstance(content, str):
                # Convert string content to block format with cache_control
                msg["content"] = [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            elif isinstance(content, list) and content:
                # Add cache_control to the last content block
                last_block = dict(content[-1])
                last_block["cache_control"] = {"type": "ephemeral"}
                content[-1] = last_block

        return system_blocks, cached_tools, cached_messages

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
    ) -> LLMResponse:
        """Execute non-streaming inference with Claude API.

        Accepts platform-native types and handles all transformations internally.

        Args:
            messages: Platform-native message objects (List[MessageInDb])
            system_prompt: System prompt for Claude
            tools: Platform-native tool objects (List[ToolRecord])
            llm_config: Model configuration (model, temperature, max_tokens, etc.)

        Returns:
            Standardized LLMResponse (transformed from Claude's response)

        """
        # Transform platform types to Claude format
        system_prompt_processed, vendor_messages = self.transform_messages_to_vendor(
            messages, system_prompt
        )
        vendor_tools = self.transform_tools_to_vendor(tools)

        # Apply prompt caching breakpoints if enabled
        prompt_caching = llm_config.get("prompt_caching", False)
        if prompt_caching:
            system_prompt_processed, vendor_tools, vendor_messages = (
                self._apply_prompt_caching(
                    system_prompt_processed, vendor_messages, vendor_tools
                )
            )

        client = self.get_client()

        # Map only operator-supplied optional settings. Anthropic alone requires
        # an explicit output-token ceiling.
        model = require_model(llm_config)

        logger.debug(
            f"Running Claude inference: model={model}, messages={len(vendor_messages)}, tools={len(vendor_tools)}, prompt_caching={prompt_caching}"
        )

        kwargs: Dict[str, Any] = {
            "system": system_prompt_processed,
            "model": model,
            "messages": vendor_messages,
            **configured_generation_params(
                llm_config,
                max_tokens_parameter="max_tokens",
                stop_sequences_parameter="stop_sequences",
                top_k_parameter="top_k",
            ),
        }
        kwargs["max_tokens"] = require_max_tokens(llm_config)

        if vendor_tools:
            kwargs["tools"] = vendor_tools

        response = await client.messages.create(**kwargs)

        # Transform to generic LLMResponse
        return self.transform_response_to_platform(response)

    async def run_streaming_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[LLMResponse]:
        """Execute streaming inference with Claude API."""
        # Transform platform types to Claude format
        system_prompt_processed, vendor_messages = self.transform_messages_to_vendor(
            messages, system_prompt
        )
        vendor_tools = self.transform_tools_to_vendor(tools)

        # Apply prompt caching breakpoints if enabled
        prompt_caching = llm_config.get("prompt_caching", False)
        if prompt_caching:
            system_prompt_processed, vendor_tools, vendor_messages = (
                self._apply_prompt_caching(
                    system_prompt_processed, vendor_messages, vendor_tools
                )
            )

        client = self.get_client()

        # Map only operator-supplied optional settings.
        model = require_model(llm_config)

        logger.debug(
            f"Running Claude streaming inference: model={model}, messages={len(vendor_messages)}, tools={len(vendor_tools)}, prompt_caching={prompt_caching}"
        )

        kwargs: Dict[str, Any] = {
            "system": system_prompt_processed,
            "model": model,
            "messages": vendor_messages,
            **configured_generation_params(
                llm_config,
                max_tokens_parameter="max_tokens",
                stop_sequences_parameter="stop_sequences",
                top_k_parameter="top_k",
            ),
        }
        kwargs["max_tokens"] = require_max_tokens(llm_config)

        if vendor_tools:
            kwargs["tools"] = vendor_tools

        # Accumulate state for building complete response
        message_id = None
        message_model = model
        content_blocks: Dict[int, LLMContentBlock] = {}  # Use dict for indexed access
        block_accumulators: Dict[
            int, Dict[str, Any]
        ] = {}  # Track accumulated data per block
        stop_reason = None
        usage_info = None

        # Use streaming context manager
        async with client.messages.stream(**kwargs) as stream:
            async for event in stream:
                event_type = event.type

                if event_type == "message_start":
                    # Extract message metadata
                    message_id = event.message.id
                    message_model = event.message.model
                    if event.message.usage:
                        usage_info = LLMUsageInfo(
                            input_tokens=event.message.usage.input_tokens,
                            output_tokens=event.message.usage.output_tokens,
                            cache_creation_input_tokens=getattr(
                                event.message.usage, "cache_creation_input_tokens", None
                            ),
                            cache_read_input_tokens=getattr(
                                event.message.usage, "cache_read_input_tokens", None
                            ),
                        )

                elif event_type == "content_block_start":
                    # New content block starting - use event.index for positioning
                    block_index = event.index
                    block = event.content_block

                    # Initialize accumulator for this block
                    block_accumulators[block_index] = {
                        "text": "",
                        "tool_json": "",
                        "thinking": "",
                        "signature": "",
                        "tool_id": None,
                        "tool_name": None,
                    }

                    if block.type == "text":
                        # Initialize empty text block at correct index
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.TEXT,
                            content=LLMTextBlock(text=""),
                        )
                    elif block.type == "thinking":
                        # Initialize empty thinking block
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.THINKING,
                            content=LLMTextBlock(text=""),  # Thinking uses text format
                        )
                    elif block.type == "tool_use":
                        # Tool use block starting
                        block_accumulators[block_index]["tool_id"] = block.id
                        block_accumulators[block_index]["tool_name"] = block.name
                        # Initialize empty tool use block
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=block.id,
                                name=block.name,
                                input={},
                            ),
                            id=block.id,
                        )

                elif event_type == "content_block_delta":
                    delta = event.delta
                    block_index = event.index

                    if delta.type == "text_delta":
                        # Accumulate text
                        block_accumulators[block_index]["text"] += delta.text
                        # Update the content block at correct index
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.TEXT,
                            content=LLMTextBlock(
                                text=block_accumulators[block_index]["text"]
                            ),
                        )

                        # Yield partial response with accumulated content
                        yield LLMResponse(
                            id=message_id or "",
                            model=message_model,
                            content=self._blocks_dict_to_list(content_blocks),
                            stop_reason=None,
                            usage=usage_info,
                            role="assistant",
                            metadata={
                                "vendor": "anthropic",
                                "streaming": True,
                                "delta": {
                                    "type": "text_delta",
                                    "block_index": block_index,
                                    "text": delta.text,
                                },
                            },
                        )

                    elif delta.type == "thinking_delta":
                        # Accumulate thinking content (extended thinking feature)
                        block_accumulators[block_index]["thinking"] += delta.thinking
                        # Update the thinking block
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.THINKING,
                            content=LLMTextBlock(
                                text=block_accumulators[block_index]["thinking"]
                            ),
                        )

                        # Yield partial response with thinking content
                        yield LLMResponse(
                            id=message_id or "",
                            model=message_model,
                            content=self._blocks_dict_to_list(content_blocks),
                            stop_reason=None,
                            usage=usage_info,
                            role="assistant",
                            metadata={
                                "vendor": "anthropic",
                                "streaming": True,
                                "delta": {
                                    "type": "thinking_delta",
                                    "block_index": block_index,
                                    "text": delta.thinking,
                                },
                            },
                        )

                    elif delta.type == "signature_delta":
                        # Signature for thinking block (verify integrity)
                        block_accumulators[block_index]["signature"] = delta.signature
                        # Signature is metadata, not yielded separately

                    elif delta.type == "input_json_delta":
                        # Accumulate tool use JSON
                        block_accumulators[block_index]["tool_json"] += (
                            delta.partial_json
                        )
                        # Don't yield partial tool use to avoid invalid JSON
                        # Tool use will be yielded when complete in content_block_stop

                elif event_type == "content_block_stop":
                    # Content block completed
                    block_index = event.index

                    if block_index in content_blocks:
                        block = content_blocks[block_index]

                        if block.type == LLMContentType.TOOL_USE:
                            # Parse accumulated JSON and update tool block
                            try:
                                tool_json = block_accumulators[block_index]["tool_json"]
                                tool_input = json.loads(tool_json) if tool_json else {}

                                content_blocks[block_index] = LLMContentBlock(
                                    type=LLMContentType.TOOL_USE,
                                    content=LLMToolUseBlock(
                                        id=block_accumulators[block_index]["tool_id"]
                                        or "",
                                        name=block_accumulators[block_index][
                                            "tool_name"
                                        ]
                                        or "",
                                        input=tool_input,
                                    ),
                                    id=block_accumulators[block_index]["tool_id"],
                                )

                                # Yield complete tool use
                                yield LLMResponse(
                                    id=message_id or "",
                                    model=message_model,
                                    content=self._blocks_dict_to_list(content_blocks),
                                    stop_reason=None,
                                    usage=usage_info,
                                    role="assistant",
                                    metadata={
                                        "vendor": "anthropic",
                                        "streaming": True,
                                        "delta": {
                                            "type": "tool_use_complete",
                                            "block_index": block_index,
                                            "tool_id": block_accumulators[block_index][
                                                "tool_id"
                                            ],
                                            "tool_name": block_accumulators[
                                                block_index
                                            ]["tool_name"],
                                            "tool_input": tool_input,
                                        },
                                    },
                                )
                            except json.JSONDecodeError as error:
                                logger.error(
                                    "Failed to parse streamed tool input index=%d "
                                    "error_type=%s",
                                    block_index,
                                    type(error).__name__,
                                )

                elif event_type == "message_delta":
                    # Update stop reason and usage (usage is cumulative)
                    if hasattr(event, "delta"):
                        stop_reason = event.delta.stop_reason
                    if hasattr(event, "usage") and event.usage:
                        # Usage in message_delta is cumulative
                        if usage_info:
                            usage_info.output_tokens = event.usage.output_tokens
                        else:
                            usage_info = LLMUsageInfo(
                                input_tokens=0,
                                output_tokens=event.usage.output_tokens,
                            )

                elif event_type == "message_stop":
                    # Streaming complete - yield final response
                    final_response = LLMResponse(
                        id=message_id or "",
                        model=message_model,
                        content=self._blocks_dict_to_list(content_blocks),
                        stop_reason=stop_reason,
                        usage=usage_info,
                        role="assistant",
                        metadata={"vendor": "anthropic", "streaming": False},
                    )
                    yield final_response
                    return

                elif event_type == "error":
                    # Handle error events
                    logger.error("Anthropic streaming provider error")
                    raise RuntimeError("Anthropic streaming request failed.") from None

                elif event_type == "ping":
                    # Ping events - ignore, just keep connection alive
                    pass

                # Handle other unknown event types gracefully (per Anthropic versioning policy)

        # Fallback yield if message_stop not received
        yield LLMResponse(
            id=message_id or "",
            model=message_model,
            content=self._blocks_dict_to_list(content_blocks),
            stop_reason=stop_reason,
            usage=usage_info,
            role="assistant",
            metadata={"vendor": "anthropic", "streaming": False},
        )

    def _blocks_dict_to_list(
        self, blocks_dict: Dict[int, LLMContentBlock]
    ) -> List[LLMContentBlock]:
        """Convert indexed content blocks dict to sorted list.

        Args:
            blocks_dict: Dictionary mapping block index to LLMContentBlock

        Returns:
            List of content blocks in index order

        """
        if not blocks_dict:
            return []

        # Sort by index and return list
        max_index = max(blocks_dict.keys())
        result = []
        for i in range(max_index + 1):
            if i in blocks_dict:
                result.append(blocks_dict[i])
        return result

    def transform_response_to_platform(
        self, vendor_response: ClaudeMessage
    ) -> LLMResponse:
        """Transform Claude response to generic LLMResponse.

        Converts vendor-specific objects (TextBlock, ToolUseBlock) into
        application-native format (LLMTextBlock, LLMToolUseBlock).

        Args:
            vendor_response: anthropic.types.Message

        Returns:
            Generic LLMResponse with application-native content blocks

        """
        from eylo.sockets.llm.schemas import LLMTextBlock, LLMToolUseBlock

        # Convert Claude content blocks to application-native content blocks
        content_blocks = []

        for block in vendor_response.content:
            block_type = self._map_claude_content_type(block.type)

            # Transform vendor objects to application-native types
            if block.type == "text":
                # Convert Anthropic TextBlock to application LLMTextBlock
                app_content = LLMTextBlock(text=block.text)  # type: ignore
                content_blocks.append(
                    LLMContentBlock(
                        type=block_type,
                        content=app_content,
                    )
                )
            elif block.type == "tool_use":
                # Convert Anthropic ToolUseBlock to application LLMToolUseBlock
                app_content = LLMToolUseBlock(
                    id=block.id,  # type: ignore
                    name=block.name,  # type: ignore
                    input=block.input,  # type: ignore
                )
                content_blocks.append(
                    LLMContentBlock(
                        type=block_type,
                        content=app_content,
                        id=block.id,  # type: ignore
                    )
                )
            else:
                # For other types, store as-is for now
                content_blocks.append(
                    LLMContentBlock(
                        type=block_type,
                        content=str(block) if not isinstance(block, dict) else block,
                    )
                )

        # Map usage info
        usage = None
        if vendor_response.usage:
            usage = LLMUsageInfo(
                input_tokens=vendor_response.usage.input_tokens,
                output_tokens=vendor_response.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    vendor_response.usage, "cache_creation_input_tokens", None
                ),
                cache_read_input_tokens=getattr(
                    vendor_response.usage, "cache_read_input_tokens", None
                ),
            )

        return LLMResponse(
            id=vendor_response.id,
            model=vendor_response.model,
            content=content_blocks,
            stop_reason=vendor_response.stop_reason,
            usage=usage,
            role=vendor_response.role,
            metadata={"vendor": "anthropic"},
        )

    def _map_claude_content_type(self, claude_type: str) -> LLMContentType:
        """Map Claude content type to generic LLMContentType."""
        mapping = {
            "text": LLMContentType.TEXT,
            "tool_use": LLMContentType.TOOL_USE,
            "thinking": LLMContentType.THINKING,
        }
        return mapping.get(claude_type, LLMContentType.TEXT)
