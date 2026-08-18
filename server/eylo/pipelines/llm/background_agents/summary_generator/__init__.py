"""Context Management Background Agent.

This module provides intelligent context management for LLM conversations:
- Background agent that monitors token usage
- Automatic summarization when approaching limits
- Token counting utilities for all vendors
- Context pruning strategies
- Context assembly with summary integration

Main Components:
- agent.py: Background agent for proactive context management
- token_counter.py: Vendor-specific token counting
- context_pruner.py: Intelligent message pruning strategies
- context_assembly.py: Smart context assembly using summaries
- utils.py: Helper functions for summarization and token management
"""

# Export main classes for easier imports
from .agent import process_context_management_request
from .token_counter import (
    AnthropicTokenCounter,
    BedrockTokenCounter,
    GeminiTokenCounter,
    OpenAITokenCounter,
    TokenCounter,
    get_token_counter,
)
from .utils import (
    MessageGroup,
    count_conversation_tokens,
    flatten_groups,
    get_max_tokens_for_model,
    group_messages_by_request,
    should_trigger_context_management,
    summarize_messages_with_llm,
)

__all__ = [
    # Agent
    "process_context_management_request",
    # Token Counting
    "TokenCounter",
    "OpenAITokenCounter",
    "AnthropicTokenCounter",
    "BedrockTokenCounter",
    "GeminiTokenCounter",
    "get_token_counter",
    # Utilities
    "MessageGroup",
    "count_conversation_tokens",
    "flatten_groups",
    "get_max_tokens_for_model",
    "group_messages_by_request",
    "should_trigger_context_management",
    "summarize_messages_with_llm",
]
