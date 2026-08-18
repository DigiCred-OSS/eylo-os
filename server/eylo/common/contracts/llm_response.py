"""Vendor-neutral LLM response and input contracts.

Shared by `sockets/` (which produces them) and `modules/` (which consumes
them), so they live here rather than in either layer.

These were previously defined twice: once here as
`sockets/llm/schemas/__init__.py` and once as `sockets/llm/schemas/llm_response.py`.
This file is the canonical set; the duplicate is gone.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMContentType(str, Enum):
    """Generic content types that can appear in LLM responses.

    These types are common across most LLM providers, though not all
    providers support all types.
    """

    TEXT = "text"
    TOOL_USE = "tool_use"
    THINKING = "thinking"
    IMAGE = "image"


class LLMTextBlock(BaseModel):
    """Generic text content from LLM - application native format."""

    text: str


class LLMToolUseBlock(BaseModel):
    """Generic tool use request from LLM - application native format.

    Represents a request from the LLM to execute a tool/function.
    """

    id: str = Field(..., description="Unique identifier for this tool use")
    name: str = Field(..., description="Name of the tool to execute")
    input: Dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the tool"
    )


class LLMContentBlock(BaseModel):
    """Generic content block from LLM response - application native format.

    This uses strongly-typed content based on the block type:
    - TEXT blocks contain LLMTextBlock
    - TOOL_USE blocks contain LLMToolUseBlock
    - Other types contain str or dict

    This ensures the application always works with a consistent,
    vendor-agnostic data structure.
    """

    type: LLMContentType
    content: Any  # LLMTextBlock, LLMToolUseBlock, str, or dict

    # Optional ID for tool use blocks
    id: Optional[str] = None


class LLMUsageInfo(BaseModel):
    """Token usage information.

    Tracks token consumption for billing and monitoring purposes.
    Not all fields are available from all vendors.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.input_tokens + self.output_tokens


class LLMResponse(BaseModel):
    """Generic LLM response - vendor-agnostic.

    This represents a normalized response from any LLM provider.
    Vendor adapters transform their specific responses into this format.

    This standardization lets platform runners process responses from any
    vendor without vendor-specific logic.
    """

    id: str = Field(..., description="Unique identifier for this response")
    model: str = Field(..., description="Model identifier used for this response")
    content: List[LLMContentBlock] = Field(
        default_factory=list, description="Content blocks in the response"
    )
    stop_reason: Optional[str] = Field(
        None,
        description="Reason the model stopped generating (e.g., 'end_turn', 'max_tokens', 'tool_use')",
    )
    usage: Optional[LLMUsageInfo] = Field(None, description="Token usage information")
    role: str = Field(default="assistant", description="Role of the message author")

    # Vendor-specific metadata can be stored here if needed
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional vendor-specific metadata",
    )
