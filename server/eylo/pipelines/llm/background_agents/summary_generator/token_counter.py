"""Token counting utilities for LLM vendors.

This module provides token counting capabilities for different LLM vendors.
Each vendor has their own tokenizer, so we need vendor-specific implementations.

Token counting is critical for:
- Preventing context overflow errors
- Pruning message history intelligently
- Estimating costs before API calls
- Optimizing context window usage
"""

import json
import logging
import math
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Dict, List

import tiktoken

from eylo.common.contracts.llm_catalog import LLMModels, LLMProviders
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.messages import MessageInDb
from eylo.modules.tools.schemas.indb import ToolInDb

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _local_encoding() -> tiktoken.Encoding | None:
    """Load the optional local tokenizer without making import depend on the web."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as error:
        logger.warning(
            "Local tokenizer unavailable; using conservative estimate error_type=%s",
            type(error).__name__,
        )
        return None


def _count_local_tokens(text: str) -> int:
    """Return a conservative local estimate without provider credentials."""
    if not text:
        return 0
    encoding = _local_encoding()
    encoded_tokens = len(encoding.encode(text)) if encoding is not None else 0
    return max(encoded_tokens, math.ceil(len(text) / 3))


class TokenCounter(ABC):
    """Abstract base class for token counting.

    Each LLM vendor has different tokenization, so we need
    vendor-specific implementations.
    """

    @abstractmethod
    def count_text_tokens(self, text: str) -> int:
        """Count tokens in plain text.

        Args:
            text: Plain text string

        Returns:
            Number of tokens

        """
        pass

    @abstractmethod
    def count_message_tokens(self, message: MessageInDb) -> int:
        """Count tokens in a single message.

        Includes overhead for message structure (role, formatting, etc.)

        Args:
            message: Platform message object

        Returns:
            Number of tokens including overhead

        """
        pass

    @abstractmethod
    def count_messages_tokens(self, messages: List[MessageInDb]) -> int:
        """Count tokens in a list of messages.

        Includes message structure overhead and conversation formatting.

        Args:
            messages: List of platform messages

        Returns:
            Total number of tokens

        """
        pass

    @abstractmethod
    def count_tool_tokens(self, tool: ToolInDb) -> int:
        """Count tokens in a tool definition.

        Args:
            tool: Platform tool object

        Returns:
            Number of tokens for this tool definition

        """
        pass

    @abstractmethod
    def count_tools_tokens(self, tools: List[ToolInDb]) -> int:
        """Count tokens in tool definitions.

        Args:
            tools: List of platform tools

        Returns:
            Total number of tokens for all tools

        """
        pass

    def count_system_prompt_tokens(self, system_prompt: str) -> int:
        """Count tokens in system prompt.

        Default implementation uses text counting, but vendors
        may override for vendor-specific formatting.

        Args:
            system_prompt: System prompt string

        Returns:
            Number of tokens

        """
        return self.count_text_tokens(system_prompt)

    def count_total_context_tokens(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolInDb],
    ) -> Dict[str, int]:
        """Count total tokens for a complete context.

        Args:
            messages: Conversation messages
            system_prompt: System prompt
            tools: Available tools

        Returns:
            Dictionary with token breakdown:
            {
                "system": int,
                "messages": int,
                "tools": int,
                "total": int,
            }

        """
        system_tokens = (
            self.count_system_prompt_tokens(system_prompt) if system_prompt else 0
        )
        messages_tokens = self.count_messages_tokens(messages)
        tools_tokens = self.count_tools_tokens(tools) if tools else 0

        total = system_tokens + messages_tokens + tools_tokens

        return {
            "system": system_tokens,
            "messages": messages_tokens,
            "tools": tools_tokens,
            "total": total,
        }

    def count_context_tokens(self, ctx: ConversationContext) -> Dict[str, int]:
        """Count total tokens for a conversation context.

        Args:
            ctx: Conversation context
        Returns:
            Dictionary with token breakdown

        """
        messages = ctx.messages or []
        system_prompt = ctx.system_prompt or ""
        tools = ctx.get_tools() or []

        return self.count_total_context_tokens(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
        )


class OpenAITokenCounter(TokenCounter):
    """Token counter for OpenAI models using tiktoken."""

    def __init__(self, model: LLMModels):
        """Initialize with model name for correct tokenizer.

        Args:
            model: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")

        """
        self.model = model
        self._encoding = self._resolve_encoding()

    def _resolve_encoding(self) -> tiktoken.Encoding | None:
        """Resolve the configured model tokenizer without requiring network access."""
        try:
            return tiktoken.encoding_for_model(self.model)
        except KeyError:
            logger.info(
                "No tokenizer registered for configured model=%s; using local estimate",
                self.model,
            )
            return _local_encoding()
        except Exception as error:
            logger.warning(
                "Configured model tokenizer unavailable; using conservative estimate "
                "model=%s error_type=%s",
                self.model,
                type(error).__name__,
            )
            return None

    def count_text_tokens(self, text: str) -> int:
        """Count tokens with the model tokenizer or a conservative local estimate."""
        if not text:
            return 0
        if self._encoding is None:
            return math.ceil(len(text) / 3)
        return len(self._encoding.encode(text))

    def count_message_tokens(self, message: MessageInDb) -> int:
        """Count tokens in a message including OpenAI formatting overhead.

        OpenAI messages have overhead:
        - Each message: ~4 tokens (role formatting)
        - Each message content: actual content tokens
        """
        # Base overhead per message
        tokens = 4  # <im_start>{role}<im_sep>{content}<im_end>

        # Use the common text extraction method
        text_content = message.get_text_content()
        if text_content:
            tokens += self.count_text_tokens(text_content)

        return tokens

    def count_messages_tokens(self, messages: List[MessageInDb]) -> int:
        """Count tokens for message array.

        Includes per-message overhead + priming tokens.
        """
        if not messages:
            return 0

        total = 0
        for msg in messages:
            total += self.count_message_tokens(msg)

        # Add priming tokens (conversation start)
        total += 3  # <im_start>assistant

        return total

    def count_tool_tokens(self, tool: ToolInDb) -> int:
        """Count tokens in a tool definition.

        OpenAI tools are JSON schema objects.
        """
        # Convert tool to OpenAI format approximation
        tool_dict = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.get_input_schema(),
            },
        }

        tool_json = json.dumps(tool_dict)
        return self.count_text_tokens(tool_json)

    def count_tools_tokens(self, tools: List[ToolInDb]) -> int:
        """Count tokens for all tool definitions."""
        if not tools:
            return 0

        return sum(self.count_tool_tokens(tool) for tool in tools)


class AnthropicTokenCounter(TokenCounter):
    """Token counter for Anthropic/Claude models."""

    def __init__(self, model: LLMModels):
        """Initialize with model name.

        Args:
            model: Claude model name

        """
        self.model = model

    def count_text_tokens(self, text: str) -> int:
        """Count Claude text with a conservative local approximation."""
        return _count_local_tokens(text)

    def count_message_tokens(self, message: MessageInDb) -> int:
        """Count tokens in a message."""
        # Anthropic message overhead is minimal
        tokens = 3  # Role and formatting

        # Use the common text extraction method
        text_content = message.get_text_content()
        if text_content:
            tokens += self.count_text_tokens(text_content)

        return tokens

    def count_messages_tokens(self, messages: List[MessageInDb]) -> int:
        """Count tokens for all messages."""
        if not messages:
            return 0

        return sum(self.count_message_tokens(msg) for msg in messages)

    def count_tool_tokens(self, tool: ToolInDb) -> int:
        """Count tokens in a tool definition."""
        tool_dict = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.get_input_schema(),
        }

        tool_json = json.dumps(tool_dict)
        return self.count_text_tokens(tool_json)

    def count_tools_tokens(self, tools: List[ToolInDb]) -> int:
        """Count tokens for all tools."""
        if not tools:
            return 0

        return sum(self.count_tool_tokens(tool) for tool in tools)


class GeminiTokenCounter(TokenCounter):
    """Token counter for Google Gemini models."""

    def __init__(self, model: LLMModels):
        """Initialize with model name.

        Args:
            model: Gemini model name

        """
        self.model = model

    def count_text_tokens(self, text: str) -> int:
        """Count Gemini text with a conservative local approximation."""
        return _count_local_tokens(text)

    def count_message_tokens(self, message: MessageInDb) -> int:
        """Count tokens in a message."""
        tokens = 2  # Minimal overhead

        # Use the common text extraction method
        text_content = message.get_text_content()
        if text_content:
            tokens += self.count_text_tokens(text_content)

        return tokens

    def count_messages_tokens(self, messages: List[MessageInDb]) -> int:
        """Count tokens for all messages."""
        if not messages:
            return 0

        return sum(self.count_message_tokens(msg) for msg in messages)

    def count_tool_tokens(self, tool: ToolInDb) -> int:
        """Count tokens in a tool definition."""
        tool_dict = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.get_input_schema(),
        }

        tool_json = json.dumps(tool_dict)
        return self.count_text_tokens(tool_json)

    def count_tools_tokens(self, tools: List[ToolInDb]) -> int:
        """Count tokens for all tools."""
        if not tools:
            return 0

        return sum(self.count_tool_tokens(tool) for tool in tools)


class BedrockTokenCounter(AnthropicTokenCounter):
    """Conservative local counter for Bedrock-hosted models."""


def get_token_counter(vendor: LLMProviders, model: LLMModels) -> TokenCounter:
    """Factory function to get the appropriate token counter.

    Args:
        vendor: LLM vendor (OPENAI, ANTHROPIC, BEDROCK, GEMINI)
        model: Model name from LLMModels enum

    Returns:
        TokenCounter instance for the vendor

    Raises:
        ValueError: If vendor is not supported

    """
    if vendor in {
        LLMProviders.OPENAI,
        LLMProviders.OPENAI_RESPONSES,
        LLMProviders.SARVAM,
    }:
        return OpenAITokenCounter(model=model)
    elif vendor == LLMProviders.ANTHROPIC:
        return AnthropicTokenCounter(model=model)
    elif vendor == LLMProviders.BEDROCK:
        return BedrockTokenCounter(model=model)
    elif vendor == LLMProviders.GEMINI:
        return GeminiTokenCounter(model=model)
    elif vendor in (LLMProviders.CEREBRAS, LLMProviders.GROQ):
        # Cerebras and Groq use OpenAI-compatible APIs
        return OpenAITokenCounter(model=model)
    else:
        raise ValueError(f"Token counting not supported for vendor: {vendor}")
