"""Google Gemini LLM vendor adapter implementation.

This module provides integration with Google's Gemini language models,
implementing the LLMVendorAdapter interface to handle all Gemini-specific
message transformations, tool formatting, and response parsing.

Architecture Notes:
- Gemini's API differs from Anthropic/OpenAI in several key ways:
  * System messages can be provided via system_instruction parameter
  * Tool calls use function_call format in response parts
  * Responses use candidates[0].content.parts structure
  * Automatic function calling is enabled by default (can be disabled)
  * Supports compositional (sequential) and parallel function calling

References:
- Gemini API: https://ai.google.dev/gemini-api/docs
- Function Calling: https://ai.google.dev/gemini-api/docs/function-calling

"""

import base64
import json
import logging
import mimetypes
import uuid
from typing import Any, AsyncIterator, Dict, Final, List, Optional, Tuple
from urllib.parse import urlparse

from google import genai
from google.genai import types

from eylo.common.contracts.messages import MessageInDb, MessageKind
from eylo.common.contracts.tool_platform import PlatformTool
from eylo.common.contracts.tool_record import ToolRecord
from eylo.sockets.common.schema_utils import clean_schema_for_gemini
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

logger = logging.getLogger(__name__)

GEMINI_IMAGE_MIME_PREFIX: Final = "image/"
GEMINI_DEFAULT_IMAGE_MIME_TYPE: Final = "image/jpeg"
GEMINI_FILE_URI_PREFIX: Final = "files/"
GEMINI_FILE_URI_HOST: Final = "generativelanguage.googleapis.com"
GEMINI_FILE_URI_PATH_FRAGMENT: Final = "/files/"

# Default safety settings for Gemini API
# BLOCK_ONLY_HIGH allows most content while still blocking extreme cases
DEFAULT_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    ),
]


class GeminiAdapter(LLMVendorAdapter):
    """Google Gemini LLM vendor adapter.

    Encapsulates all Gemini-specific logic for message transformation,
    tool formatting, and response parsing.

    Key Differences from Anthropic/OpenAI:
    - System instructions are separate from messages
    - Tool calls use function_call format in response parts
    - Responses use candidates[0].content.parts structure
    - Automatic function calling is enabled by default (can be disabled)
    - Supports compositional (sequential) and parallel function calling
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_client(self) -> genai.Client:
        """Get authenticated Gemini client."""
        return genai.Client(api_key=self._api_key)

    def _requires_thought_signature(self, model: str) -> bool:
        """Check if model version requires thought_signature field.

        Gemini 2.0+ and 3.0+ models require thought_signature in
        function_call and function_response parts for tool calling.

        Args:
            model: Model identifier (e.g., 'gemini-2.0-flash-exp', 'gemini-3-flash')

        Returns:
            True if model requires thought_signature, False otherwise

        """
        if not model:
            return False

        model_lower = model.lower()
        # Match gemini-2.0, gemini-2.5, gemini-3.0, etc.
        # Pattern: gemini-<major>.<minor> or gemini-<major>-
        if "gemini-2." in model_lower or "gemini-2-" in model_lower:
            return True
        if "gemini-3" in model_lower:
            return True

        return False

    def _get_thought_signature(
        self, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Extract thought signature from message metadata."""
        thought_signature = ""  # Default to empty string

        if not metadata:
            return thought_signature

        # 1. Check for direct thought_signature key
        if "thought_signature" in metadata:
            thought_signature = metadata["thought_signature"]

        # 2. Check for thought_signature in nested metadata (as stored in DB)
        # The complete LLM response structure includes a metadata field
        if "metadata" in metadata:
            response_meta = metadata["metadata"]
            if isinstance(response_meta, dict) and "thought_signature" in response_meta:
                thought_signature = response_meta["thought_signature"]

        # 3. Check for thought_signature in llm_response wrapper
        if "llm_response" in metadata:
            llm_response = metadata["llm_response"]
            if isinstance(llm_response, dict):
                # Check in response metadata
                if "metadata" in llm_response:
                    response_meta = llm_response["metadata"]
                    if (
                        isinstance(response_meta, dict)
                        and "thought_signature" in response_meta
                    ):
                        thought_signature = response_meta["thought_signature"]

                # Check at top level
                if "thought_signature" in llm_response:
                    thought_signature = llm_response["thought_signature"]

        # Normalize to base64 if needed
        thought_signature = self._normalize_thought_signature_to_b64(thought_signature)

        return thought_signature

    def _normalize_thought_signature_to_b64(self, sig: Any) -> str:
        """Convert incoming thought_signature to a base64-encoded ASCII string
        so it can be safely stored in JSON/DB.
        """
        if not sig:
            return ""
        if isinstance(sig, bytes):
            return base64.b64encode(sig).decode("ascii")
        if isinstance(sig, str):
            try:
                # If it's already valid base64, keep as-is
                base64.b64decode(sig, validate=True)
                return sig
            except Exception:
                return base64.b64encode(sig.encode("utf-8", "ignore")).decode("ascii")
        return base64.b64encode(str(sig).encode("utf-8", "ignore")).decode("ascii")

    def transform_messages_to_vendor(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        model: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transform Eylo messages to Gemini format.

        Gemini expects:
        - System instruction separate from messages
        - Messages with role: "user" | "model" (assistant)
        - Parts array containing text, function_call, or function_response
        - Tool use and tool results as specific part types

        Args:
            messages: Platform-native message objects
            system_prompt: System instruction for Gemini
            model: Model identifier (optional, used to determine if thought_signature needed)

        Returns:
            Tuple of (system_prompt, vendor_messages)
            system_prompt is returned for use in system_instruction parameter

        """
        # Validate message sequence
        messages = self._validate_message_sequence(messages)

        # Check if this model requires thought signatures
        requires_thought_sig = (
            self._requires_thought_signature(model) if model else False
        )

        vendor_messages = []

        for msg in messages:
            if msg.kind == MessageKind.USER:
                vendor_messages.append(
                    {
                        "role": "user",
                        "parts": self._format_user_parts(msg.content),
                    }
                )

            elif msg.kind == MessageKind.ASSISTANT:
                vendor_messages.append(
                    {
                        "role": "model",  # Gemini uses "model" instead of "assistant"
                        "parts": self._format_assistant_parts(
                            msg, requires_thought_sig
                        ),
                    }
                )

            elif msg.kind == MessageKind.TOOL_USE:
                # Gemini represents tool use as model message with function_call parts
                try:
                    parsed_msg = msg.get_tool_use_content()
                    tool_use = parsed_msg.content

                    # Build function_call dict
                    function_call = {
                        "name": tool_use.name,
                        "args": tool_use.input,
                    }

                    function_call_part = {
                        "function_call": function_call,
                    }

                    # Add thoughtSignature if model requires it
                    if requires_thought_sig:
                        thought_sig = self._get_thought_signature(msg.meta)
                        if thought_sig:
                            function_call_part["thoughtSignature"] = thought_sig

                    vendor_messages.append(
                        {
                            "role": "model",
                            "parts": [function_call_part],
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
                # Gemini expects tool results as user messages with function_response parts
                try:
                    parsed_msg = msg.get_tool_result_content()
                    if not parsed_msg.content:
                        logger.warning(
                            f"TOOL_RESULT message {msg.id} has empty content"
                        )
                        continue

                    tool_result = parsed_msg.content[0]

                    # Build function_response dict
                    function_response = {
                        "name": tool_result.tool_use_id,  # Gemini uses name field
                        "response": self._serialize_tool_content(tool_result.content),
                    }

                    vendor_messages.append(
                        {
                            "role": "user",  # Tool results come as user messages
                            "parts": [{"function_response": function_response}],
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

    def _format_user_parts(self, content: Any) -> List[Dict[str, Any]]:
        """Format one typed user message as Gemini parts."""
        from eylo.common.contracts.message_content import (
            ImageUrlContent,
            TextContent,
            UserMessageContent,
            WidgetResponseMessageContent,
        )

        if isinstance(content, UserMessageContent):
            parts = []
            for block in content.content:
                if isinstance(block, TextContent):
                    parts.append({"text": block.text})
                elif isinstance(block, ImageUrlContent):
                    parts.append(
                        self._format_image_url_part(
                            block.image_url.url,
                            block.image_url.mime_type,
                        )
                    )
            return parts
        if isinstance(content, WidgetResponseMessageContent):
            return [{"text": content.get_text_content()}]
        raise TypeError(
            f"Unsupported typed user content: {type(content).__name__}"
        )

    def _format_image_url_part(
        self,
        image_url: str,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a remote image URL as a Gemini file data part."""
        self._validate_gemini_file_uri(image_url)
        concrete_mime_type = mime_type or self._guess_image_mime_type(image_url)
        return {"file_data": {"file_uri": image_url, "mime_type": concrete_mime_type}}

    @staticmethod
    def _validate_gemini_file_uri(image_url: str) -> None:
        """Ensure image URL is a Gemini Files API URI before emitting file_data."""
        parsed = urlparse(image_url)
        is_relative_file_uri = image_url.startswith(GEMINI_FILE_URI_PREFIX)
        is_google_file_uri = (
            parsed.scheme in {"http", "https"}
            and parsed.netloc == GEMINI_FILE_URI_HOST
            and GEMINI_FILE_URI_PATH_FRAGMENT in parsed.path
        )
        if is_relative_file_uri or is_google_file_uri:
            return
        raise ValueError(
            "Gemini image_url content requires a Gemini Files API URI; "
            "arbitrary HTTP image URLs are not supported by file_data"
        )

    @staticmethod
    def _guess_image_mime_type(image_url: str) -> str:
        """Infer the concrete Gemini MIME type from an image URL path."""
        mime_type, _ = mimetypes.guess_type(urlparse(image_url).path)
        if mime_type and mime_type.startswith(GEMINI_IMAGE_MIME_PREFIX):
            return mime_type
        return GEMINI_DEFAULT_IMAGE_MIME_TYPE

    def _format_assistant_parts(
        self, message: MessageInDb, requires_thought_sig: bool
    ) -> List[Dict[str, Any]]:
        """Format assistant message content as Gemini parts.

        Handles:
        - AssistantMessageContent: {"role": "assistant", "content": TextContent | dict}
        - ToolUseMessageContent: {"role": "tool_use", "content": ToolUseContent}
        """
        from eylo.common.contracts.message_content import (
            AssistantMessageContent,
            ImageUrlContent,
            TextContent,
            WidgetMessageContent,
        )

        parts = []

        content = message.content
        meta = message.meta

        if isinstance(content, AssistantMessageContent):
            for index, block in enumerate(content.content):
                if isinstance(block, TextContent):
                    part_item = {"text": block.text}
                elif isinstance(block, ImageUrlContent):
                    part_item = self._format_image_url_part(
                        block.image_url.url,
                        block.image_url.mime_type,
                    )
                else:
                    raise TypeError(
                        "Unsupported typed assistant content block: "
                        f"{type(block).__name__}"
                    )

                if requires_thought_sig and index == 0 and "text" in part_item:
                    thought_sig = self._get_thought_signature(meta)
                    if thought_sig:
                        part_item["thoughtSignature"] = thought_sig

                parts.append(part_item)
            return parts
        if isinstance(content, WidgetMessageContent):
            return [{"text": content.get_text_content()}]
        raise TypeError(
            f"Unsupported typed assistant content: {type(content).__name__}"
        )

    def transform_tools_to_vendor(
        self, tools: List[ToolRecord]
    ) -> List[Dict[str, Any]]:
        """Transform platform-native tools to Gemini format.

        Gemini tool format:
        {
            "function_declarations": [
                {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": {
                        "type": "object",
                        "properties": {...},
                        "required": [...]
                    }
                }
            ]
        }
        """
        function_declarations = []

        for tool in tools:
            try:
                if not tool.llm_config:
                    logger.warning(f"Tool {tool.id} has no llm_config, skipping")
                    continue

                platform_tool = tool.llm_config
                if isinstance(platform_tool, PlatformTool):
                    # Gemini uses "parameters" instead of "input_schema"
                    # Clean the schema to remove Pydantic-specific fields
                    parameters = clean_schema_for_gemini(
                        platform_tool.input_schema.to_json_schema()
                    )

                    function_declarations.append(
                        {
                            "name": platform_tool.name,
                            "description": platform_tool.description,
                            "parameters": parameters,
                        }
                    )
                else:
                    logger.error(
                        f"Unexpected llm_config type for tool {tool.id}: {type(tool.llm_config)}"
                    )
                    continue

            except Exception as error:
                logger.error(
                    "Tool transformation failed tool=%s error_type=%s",
                    tool.id,
                    type(error).__name__,
                )
                continue

        # Wrap in Gemini Tool structure
        return (
            [{"function_declarations": function_declarations}]
            if function_declarations
            else []
        )

    def _serialize_tool_content(self, content: Any) -> Dict[str, Any]:
        """Serialize tool content for Gemini.

        Gemini expects function responses as dictionaries.
        """
        if isinstance(content, dict):
            return content
        elif isinstance(content, str):
            try:
                # Try to parse JSON strings
                return json.loads(content)
            except json.JSONDecodeError:
                # Return as text response
                return {"result": content}
        elif isinstance(content, list):
            return {"result": content}
        else:
            return {"result": str(content)}

    async def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> LLMResponse:
        """Execute inference with Gemini API.

        Accepts platform-native types and handles all transformations internally.

        Args:
            messages: Platform-native message objects (List[MessageInDb])
            system_prompt: System instruction for Gemini
            tools: Platform-native tool objects (List[ToolRecord])
            llm_config: Model configuration (model, temperature, max_tokens, etc.)
            stream: Whether to stream the response (not yet implemented)

        Returns:
            Standardized LLMResponse (transformed from Gemini's response)

        """
        client = self.get_client()

        # Extract model first for message transformation
        model = require_model(llm_config)

        # Prepare inference configuration
        model, gemini_contents, config, vendor_tools = self._prepare_inference_config(
            messages, system_prompt, tools, llm_config, model
        )

        logger.debug(
            f"Running Gemini inference: model={model}, messages={len(gemini_contents)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        try:
            response = client.models.generate_content(
                model=model,
                contents=gemini_contents,
                config=config,
            )

            # Transform response to platform format
            return self.transform_response_to_platform(response)

        except Exception as error:
            logger.error(
                "Gemini API request failed error_type=%s",
                type(error).__name__,
            )
            raise

    async def run_streaming_inference(  # type: ignore[override]
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[LLMResponse]:
        """Execute streaming inference with Gemini API."""
        client = self.get_client()

        # Extract model first for message transformation
        model = require_model(llm_config)

        # Prepare inference configuration
        model, gemini_contents, config, vendor_tools = self._prepare_inference_config(
            messages, system_prompt, tools, llm_config, model
        )

        logger.debug(
            f"Running Gemini streaming inference: model={model}, messages={len(gemini_contents)}, "
            f"tools={len(vendor_tools) if vendor_tools else 0}"
        )

        try:
            # Track streaming state
            content_blocks: Dict[int, LLMContentBlock] = {}
            block_accumulators: Dict[int, Dict[str, Any]] = {}
            message_id = None
            finish_reason = None
            usage_info = None
            thought_signature = ""

            # Make streaming API call
            async for chunk in await client.aio.models.generate_content_stream(
                model=model,
                contents=gemini_contents,
                config=config,
            ):
                # Extract message ID if available
                if hasattr(chunk, "response_id") and chunk.response_id:
                    message_id = chunk.response_id

                # Process chunk and build content blocks
                if not chunk.candidates or len(chunk.candidates) == 0:
                    continue

                candidate = chunk.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    continue

                # Process parts in this chunk
                for part_idx, part in enumerate(candidate.content.parts):
                    # Use part index as block index
                    block_index = part_idx

                    # Initialize accumulator if needed
                    if block_index not in block_accumulators:
                        block_accumulators[block_index] = {
                            "text": "",
                            "tool_args": {},
                            "tool_id": None,
                            "tool_name": None,
                        }

                    # Handle text parts
                    if hasattr(part, "text") and part.text:
                        block_accumulators[block_index]["text"] += part.text

                        # Get thought signature from part. Optional for text but improves LLM results
                        thought_signature_raw = getattr(part, "thought_signature", None)
                        thought_signature_b64 = (
                            self._normalize_thought_signature_to_b64(
                                thought_signature_raw
                            )
                            if thought_signature_raw is not None
                            else ""
                        )
                        if thought_signature_b64:
                            thought_signature = thought_signature_b64

                        # Update text block
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.TEXT,
                            content=LLMTextBlock(
                                text=block_accumulators[block_index]["text"]
                            ),
                        )

                        # Yield streaming response
                        yield LLMResponse(
                            id=message_id or str(uuid.uuid4()),
                            model=model,
                            content=self._blocks_dict_to_list(content_blocks),
                            stop_reason=None,
                            usage=usage_info,
                            role="assistant",
                            metadata={
                                "vendor": "gemini",
                                "streaming": True,
                                "delta": {
                                    "type": "text_delta",
                                    "block_index": block_index,
                                    "text": part.text,
                                },
                            },
                        )

                    # Handle function calls (tool use)
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        raw_tool_name = fc.name or "unknown"
                        # Prefer provided id if present; otherwise make a unique id (do not reuse tool name to avoid external_id collisions)
                        tool_use_id = (
                            getattr(fc, "id", None)
                            or f"{raw_tool_name}__{uuid.uuid4()}"
                        )

                        # Initialize tool accumulator if this is first chunk for this tool
                        if block_accumulators[block_index]["tool_id"] is None:
                            block_accumulators[block_index]["tool_id"] = tool_use_id
                            block_accumulators[block_index]["tool_name"] = raw_tool_name

                        fc_args = getattr(fc, "args", {})

                        logger.debug(
                            "Gemini streamed function call block_index=%d",
                            block_index,
                        )

                        # function_call id=None args={} name='get_resource_hierarchy__0197f2dd' partial_args=None will_continue=None

                        # Accumulate tool arguments directly in dictionary
                        # Merge arguments directly into the accumulator's dictionary
                        block_accumulators[block_index]["tool_args"].update(fc_args)

                        tool_input = block_accumulators[block_index]["tool_args"]

                        # Get thought signature from part. Needed for gemini 3 flash functionCall parts
                        thought_signature_raw = getattr(part, "thought_signature", None)
                        thought_signature_b64 = (
                            self._normalize_thought_signature_to_b64(
                                thought_signature_raw
                            )
                            if thought_signature_raw is not None
                            else ""
                        )
                        if thought_signature_b64:
                            thought_signature = thought_signature_b64

                        # Update tool use block
                        content_blocks[block_index] = LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=tool_use_id,
                                name=raw_tool_name,
                                input=tool_input,
                            ),
                            id=tool_use_id,
                        )

                        # Yield streaming response with tool use
                        yield LLMResponse(
                            id=message_id or str(uuid.uuid4()),
                            model=model,
                            content=self._blocks_dict_to_list(content_blocks),
                            stop_reason=None,
                            usage=usage_info,
                            role="assistant",
                            metadata={
                                "vendor": "gemini",
                                "streaming": True,
                                "delta": {
                                    "type": "tool_use_delta",
                                    "block_index": block_index,
                                    "tool_id": tool_use_id,
                                },
                                "thought_signature": thought_signature_b64,
                            },
                        )

                # Extract usage metadata from chunk
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    usage_info = LLMUsageInfo(
                        input_tokens=getattr(
                            chunk.usage_metadata, "prompt_token_count", 0
                        ),
                        output_tokens=getattr(
                            chunk.usage_metadata, "candidates_token_count", 0
                        ),
                        cache_read_input_tokens=getattr(
                            chunk.usage_metadata, "cached_content_token_count", None
                        ),
                        reasoning_tokens=getattr(
                            chunk.usage_metadata, "thoughts_token_count", None
                        ),
                    )

                # Determine finish reason
                if hasattr(candidate, "finish_reason") and candidate.finish_reason:
                    finish_reason = self._map_finish_reason(candidate.finish_reason)

            # Yield final response with finish reason
            if finish_reason:
                yield LLMResponse(
                    id=message_id or str(uuid.uuid4()),
                    model=model,
                    content=self._blocks_dict_to_list(content_blocks),
                    stop_reason=finish_reason,
                    usage=usage_info,
                    role="assistant",
                    metadata={
                        "vendor": "gemini",
                        "streaming": True,
                        "thought_signature": thought_signature,
                        "final": True,
                    },
                )

        except Exception as error:
            logger.error(
                "Gemini streaming request failed error_type=%s",
                type(error).__name__,
            )
            raise

    def _blocks_dict_to_list(
        self, blocks_dict: Dict[int, LLMContentBlock]
    ) -> List[LLMContentBlock]:
        """Convert content blocks dictionary to a sorted list.

        Used during streaming inference to maintain consistent block ordering when
        accumulating chunks by their indices. As streaming chunks arrive, blocks
        are stored in a dictionary keyed by index for efficient random access.
        This method converts the dict to a properly ordered list for the final response.

        Args:
            blocks_dict: Dictionary mapping block indices to content blocks.
                        Keys are integers representing block positions.

        Returns:
            List of content blocks sorted by index in ascending order.
            Empty list if blocks_dict is empty.

        """
        if not blocks_dict:
            return []
        # Sort by index and return just the blocks
        return [blocks_dict[i] for i in sorted(blocks_dict.keys())]

    def transform_response_to_platform(self, vendor_response: Any) -> LLMResponse:
        """Transform Gemini response to platform-native LLMResponse.

        Gemini response structure:
        {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "response text"},
                        {"function_call": {"name": "...", "args": {...}}}
                    ]
                },
                "finish_reason": "STOP"
            }],
            "usage_metadata": {
                "prompt_token_count": 10,
                "candidates_token_count": 20,
                "total_token_count": 30
            }
        }
        """
        try:
            # Extract first candidate
            if not vendor_response.candidates or len(vendor_response.candidates) == 0:
                # Return empty response
                return LLMResponse(
                    id=getattr(vendor_response, "id", "unknown"),
                    model=getattr(vendor_response, "model", "gemini-unknown"),
                    content=[],
                    stop_reason="error",
                    usage=None,
                    metadata={"vendor": "gemini", "error": "no_candidates"},
                )

            candidate = vendor_response.candidates[0]
            content = candidate.content

            # Build content blocks from parts
            content_blocks: List[LLMContentBlock] = []

            # Handle case where content.parts is None (empty response or safety filter)
            if content.parts is None:
                finish_reason = getattr(candidate, "finish_reason", None)
                safety_ratings = getattr(candidate, "safety_ratings", [])

                # Build metadata with safety information
                metadata = {
                    "vendor": "gemini",
                    "finish_reason": str(finish_reason) if finish_reason else None,
                    "error": "empty_response_parts",
                }

                # Include safety ratings if available
                if safety_ratings:
                    metadata["safety_ratings"] = [
                        {
                            "category": str(rating.category)
                            if hasattr(rating, "category")
                            else "unknown",
                            "probability": str(rating.probability)
                            if hasattr(rating, "probability")
                            else "unknown",
                        }
                        for rating in safety_ratings
                    ]

                return LLMResponse(
                    id=getattr(vendor_response, "id", f"gemini-{uuid.uuid4()}"),
                    model=getattr(vendor_response, "model_version", "gemini-unknown"),
                    content=[],
                    stop_reason=self._map_finish_reason(finish_reason),
                    usage=None,
                    metadata=metadata,
                )

            for part in content.parts:
                # Check for text
                if hasattr(part, "text") and part.text:
                    content_blocks.append(
                        LLMContentBlock(
                            type=LLMContentType.TEXT,
                            content=LLMTextBlock(text=part.text),
                        )
                    )

                # Check for function_call
                elif hasattr(part, "function_call") and part.function_call:
                    func_call = part.function_call
                    # Generate a unique ID for the tool use (Gemini doesn't provide one)
                    tool_use_id = str(uuid.uuid4())

                    content_blocks.append(
                        LLMContentBlock(
                            type=LLMContentType.TOOL_USE,
                            content=LLMToolUseBlock(
                                id=tool_use_id,
                                name=func_call.name,
                                input=dict(func_call.args) if func_call.args else {},
                            ),
                            id=tool_use_id,
                        )
                    )

            # Extract usage info
            usage = None
            if (
                hasattr(vendor_response, "usage_metadata")
                and vendor_response.usage_metadata
            ):
                usage_meta = vendor_response.usage_metadata
                usage = LLMUsageInfo(
                    input_tokens=getattr(usage_meta, "prompt_token_count", 0),
                    output_tokens=getattr(usage_meta, "candidates_token_count", 0),
                    cache_read_input_tokens=getattr(
                        usage_meta, "cached_content_token_count", None
                    ),
                    reasoning_tokens=getattr(usage_meta, "thoughts_token_count", None),
                )

            # Map finish reason
            finish_reason = getattr(candidate, "finish_reason", None)
            stop_reason = self._map_finish_reason(finish_reason)

            return LLMResponse(
                id=getattr(vendor_response, "id", f"gemini-{uuid.uuid4()}"),
                model=getattr(vendor_response, "model_version", "gemini-unknown"),
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage,
                role="assistant",
                metadata={
                    "vendor": "gemini",
                    "finish_reason": str(finish_reason) if finish_reason else None,
                },
            )

        except Exception as error:
            logger.error(
                "Gemini response transformation failed error_type=%s",
                type(error).__name__,
            )
            raise

    def _prepare_inference_config(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Tuple[
        str, List[types.Content], types.GenerateContentConfig, Optional[List[Any]]
    ]:
        """Prepare inference configuration for both streaming and non-streaming calls.

        Extracts common setup logic for Gemini API calls including message transformation,
        config extraction, and Content object creation.

        Args:
            messages: Platform-native message objects
            system_prompt: System instruction for Gemini
            tools: Platform-native tool objects
            llm_config: Model configuration dict
            model: Model identifier (optional, extracted from llm_config if not provided)

        Returns:
            Tuple of (model, gemini_contents, config, vendor_tools)

        """
        # Extract model if not provided
        if not model:
            model = require_model(llm_config)

        # Transform platform types to Gemini format (pass model for thought_signature handling)
        system_instruction, vendor_messages = self.transform_messages_to_vendor(
            messages, system_prompt, model
        )
        vendor_tools = self.transform_tools_to_vendor(tools)

        generation_params = configured_generation_params(
            llm_config,
            max_tokens_parameter="max_output_tokens",
            stop_sequences_parameter="stop_sequences",
            top_k_parameter="top_k",
        )

        # Safety settings - use permissive defaults unless specified
        safety_settings = llm_config.get("safety_settings", DEFAULT_SAFETY_SETTINGS)

        # Build config
        config = types.GenerateContentConfig(
            **generation_params,
            system_instruction=system_instruction if system_instruction else None,
            safety_settings=safety_settings,
        )

        config.thinking_config = types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL
        )

        # Add tools if available
        if vendor_tools:
            config.tools = vendor_tools
            # Disable automatic function calling - we want manual control
            config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        # Convert vendor_messages to proper Content types for Gemini SDK
        gemini_contents = []
        for msg in vendor_messages:
            gemini_contents.append(
                types.Content(
                    role=msg["role"],
                    parts=msg["parts"],
                )
            )

        return model, gemini_contents, config, vendor_tools

    def _map_finish_reason(self, gemini_reason: Any) -> str:
        """Map Gemini finish reasons to platform stop reasons.

        Gemini finish reasons (enum values):
        - STOP: Natural stop point
        - MAX_TOKENS: Max tokens reached
        - SAFETY: Content filtered for safety
        - RECITATION: Content filtered for recitation
        - OTHER: Other reason
        """
        if gemini_reason is None:
            return "unknown"

        # Convert enum to string if needed
        reason_str = str(gemini_reason).upper()

        mapping = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
            "OTHER": "other",
        }

        # Try to match the reason
        for key, value in mapping.items():
            if key in reason_str:
                return value

        return reason_str.lower()
