"""Public exports for the `llm` socket package."""

from eylo.sockets.llm.base import LLMVendorAdapter
from eylo.sockets.llm.factory import LLMFactory
from eylo.sockets.llm.schemas import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
    LLMUsageInfo,
)
from eylo.sockets.llm.vendors.anthropic import AnthropicAdapter
from eylo.sockets.llm.vendors.bedrock import AWSBedrockAdapter
from eylo.sockets.llm.vendors.gemini import GeminiAdapter
from eylo.sockets.llm.vendors.openai import OpenAIAdapter

__all__ = [
    # Base classes
    "LLMVendorAdapter",
    # Schemas - Output
    "LLMResponse",
    "LLMContentBlock",
    "LLMContentType",
    "LLMTextBlock",
    "LLMToolUseBlock",
    "LLMUsageInfo",
    # Vendor adapters
    "AnthropicAdapter",
    "AWSBedrockAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    # Factory
    "LLMFactory",
]
