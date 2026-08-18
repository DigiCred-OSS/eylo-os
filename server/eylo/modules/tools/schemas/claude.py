"""Data contracts for the `tools` domain."""

from typing import Any, Iterable, Literal, Optional, TypeAlias, Union

from anthropic.types import Message
from anthropic.types.content_block import ContentBlock
from anthropic.types.text_block import TextBlock
from anthropic.types.tool_use_block import ToolUseBlock
from pydantic import BaseModel, Field

from eylo.common.schemas import CaseInSensitiveEnum

ObjectJsonSchema: TypeAlias = dict[str, Any]

ClaudeContentBlock: TypeAlias = ContentBlock
ClaudeToolUseBlock: TypeAlias = ToolUseBlock
ClaudeTextBlock: TypeAlias = TextBlock


class ClaudeToolInputSchema(BaseModel):
    type: Literal["object"] = Field("object")
    properties: ObjectJsonSchema = Field(
        ...,
        description="The properties of the input schema. Should be a valid JSON schema.",
    )
    required: Optional[list[str]] = Field(
        [],
        description="The required properties of the input schema. Should be a valid JSON schema.",
    )


class ClaudeTool(BaseModel):
    """Copied from -
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "The unit of temperature, either \"celsius\" or \"fahrenheit\""
                }
            },
            "required": ["location"]
        }
    }
    """

    name: str = Field(
        ...,
        description="The name of the tool. Should be unique and descriptive.",
    )
    description: str = Field(
        ...,
        description="A short description of what the tool does.",
    )
    input_schema: ClaudeToolInputSchema = Field(
        ...,
        description="The input schema for the tool. Should be a valid JSON schema.",
    )


class ClaudeToolUsage(BaseModel):
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    input_tokens: int
    output_tokens: int


class ClaudeToolCallResponse(BaseModel):
    id: str
    type: Literal["tool_result"]
    cache_control: Optional[Any]
    content: Union[str, Iterable[ClaudeTextBlock]]
    is_error: bool
    model: str
    role: Literal["assistant"]
    stop_reason: Optional[str]
    stop_sequence: Optional[str]
    type: str
    usage: ClaudeToolUsage


class ClaudeContentType(CaseInSensitiveEnum):
    # Supported kinds are tool use, thinking, and redacted thinking.
    TOOL_USE = "tool_use"
    THINKING = "thinking"
    REDACTED_THINKING = "redacted_thinking"
    TEXT = "text"


class ClaudeResponse(Message):
    pass
