"""Provider-neutral LLM tool definition contracts."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlatformToolInputSchema(BaseModel):
    """Platform-native tool input schema.

    Based on JSON Schema standard, making it easy to transform
    to any vendor's expected format.

    Example::

        schema = PlatformToolInputSchema(
            type="object",
            properties={
                "location": {
                    "type": "string",
                    "description": "City name"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"]
                }
            },
            required=["location"]
        )
        ```

    """

    type: Literal["object"] = "object"
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema properties for tool inputs",
    )
    defs: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="$defs",
        description="Reusable JSON Schema definitions referenced by $ref.",
    )
    required: Optional[List[str]] = Field(
        default_factory=list,
        description="Required property names",
    )
    one_of: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        alias="oneOf",
        description="Alternative component-specific schemas for this tool input.",
    )
    discriminator: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema discriminator metadata for union-style tool inputs.",
    )
    additional_properties: Optional[bool] = Field(
        None,
        alias="additionalProperties",
        description="Whether additional properties are allowed",
    )

    def to_json_schema(self) -> Dict[str, Any]:
        """Return a vendor-ready JSON Schema dictionary."""
        return self.model_dump(by_alias=True, exclude_none=True)


class PlatformTool(BaseModel):
    """Platform-native tool definition - vendor-agnostic.

    This is the canonical format for tools in the Eylo platform.
    All tools are stored in this format and vendor adapters transform
    them to vendor-specific formats when needed.

    Example::

        tool = PlatformTool(
            name="get_weather",
            description="Get weather for a location",
            input_schema=PlatformToolInputSchema(
                type="object",
                properties={
                    "location": {"type": "string", "description": "City name"}
                },
                required=["location"]
            )
        )
        ```

    """

    name: str = Field(..., description="Unique tool name for the LLM to reference")
    description: str = Field(
        ..., description="Clear description of what the tool does for the LLM"
    )
    input_schema: PlatformToolInputSchema = Field(
        ..., description="JSON Schema defining the tool's input parameters"
    )


class PlatformToolUse(BaseModel):
    """Platform-native tool use request from LLM.

    Represents a request from any LLM vendor to execute a tool.
    Vendor adapters transform their specific formats to this:
    - Claude ToolUseBlock -> PlatformToolUse
    - OpenAI FunctionCall -> PlatformToolUse
    - Gemini FunctionCall -> PlatformToolUse

    Example::

        tool_use = PlatformToolUse(
            id="toolu_01A09q90qw90lq917835lq9",
            name="get_weather",
            input={"location": "San Francisco, CA", "unit": "fahrenheit"}
        )
        ```

    """

    id: str = Field(
        ...,
        description="Unique identifier for this tool use request. Used to match results.",
    )
    name: str = Field(
        ...,
        description="Name of the tool to execute. Must match a registered tool.",
    )
    input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the tool, validated against tool's input_schema",
    )


class PlatformToolResult(BaseModel):
    """Platform-native tool execution result.

    Represents the result of executing a tool, in a format
    that can be transformed to any vendor's expected format.

    Example::

        result = PlatformToolResult(
            tool_use_id="toolu_01A09q90qw90lq917835lq9",
            content="The weather in San Francisco is 72°F and sunny.",
            is_error=False
        )
        ```

    """

    tool_use_id: str = Field(
        ...,
        description="ID of the tool use this result corresponds to",
    )
    content: str = Field(
        ...,
        description="Tool execution result as a string. Can be JSON, markdown, or plain text.",
    )
    is_error: bool = Field(
        default=False,
        description="Whether the tool execution failed",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata about the execution (timing, retries, etc.)",
    )
    model_config = ConfigDict(extra="allow", populate_by_name=True)
