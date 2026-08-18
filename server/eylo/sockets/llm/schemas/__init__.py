"""Vendor-neutral LLM schemas.

Re-exported from `eylo.common.contracts.llm_response`, where they live so that
both `sockets/` and `modules/` can import them without either depending on the
other.

Kept as a re-export so vendor adapters need no change.
"""

from eylo.common.contracts.llm_response import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
    LLMUsageInfo,
)

__all__ = [
    "LLMContentBlock",
    "LLMContentType",
    "LLMResponse",
    "LLMTextBlock",
    "LLMToolUseBlock",
    "LLMUsageInfo",
]
