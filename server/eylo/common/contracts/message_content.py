"""Message Content Schemas - Platform-Native Formats.

These schemas define the structure of message content stored in the database.
They provide type safety and validation for all message types.

The database stores message.content as JSONB, which should conform to these schemas.
"""

import json
import re
from typing import Any, Dict, Final, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Annotated

from eylo.common.markdown import md_to_html

TEXT_CONTENT_TYPE: Final = "text"
IMAGE_URL_CONTENT_TYPE: Final = "image_url"
IMAGE_MIME_PREFIX: Final = "image/"
IMAGE_MIME_WILDCARD: Final = "image/*"
TOOL_USE_CONTENT_TYPE: Final = "tool_use"
TOOL_RESULT_CONTENT_TYPE: Final = "tool_result"
USER_ROLE: Final = "user"
ASSISTANT_ROLE: Final = "assistant"
TOOL_USE_ROLE: Final = "tool_use"
SYSTEM_ROLE: Final = "system"


def _to_pretty_json(value: Any) -> str:
    """Render structured values as stable pretty JSON for LLM-facing text."""
    return json.dumps(value, indent=2, sort_keys=True, default=str)


class TextContent(BaseModel):
    """Text content block in a message."""

    type: Literal["text"] = TEXT_CONTENT_TYPE
    text: str = Field(..., description="The text content")


class ImageUrlPayload(BaseModel):
    """URL payload for an image content block."""

    url: str = Field(..., description="HTTP(S) URL for the image")
    mime_type: Optional[str] = Field(
        default=None,
        description="Concrete image MIME type, for vendors that require it",
    )

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: Optional[str]) -> Optional[str]:
        """Validate optional image MIME type metadata."""
        if value is None:
            return value
        if not value.startswith(IMAGE_MIME_PREFIX) or value == IMAGE_MIME_WILDCARD:
            raise ValueError("mime_type must be a concrete image MIME type")
        return value


class ImageUrlContent(BaseModel):
    """Image URL content block in a message."""

    type: Literal["image_url"] = IMAGE_URL_CONTENT_TYPE
    image_url: ImageUrlPayload = Field(..., description="Image URL payload")


TextMessageContentBlock = Annotated[
    Union[TextContent, ImageUrlContent],
    Field(discriminator="type"),
]
TextMessageContentBlocks = List[TextMessageContentBlock]


def normalize_text_content_blocks(value: Any) -> TextMessageContentBlocks:
    """Normalize supported text inputs into platform-native content blocks."""
    if isinstance(value, str):
        return [TextContent(text=value)]

    if isinstance(value, TextContent | ImageUrlContent):
        return [value]

    if isinstance(value, list):
        return [_normalize_text_content_block(block) for block in value]

    return [_normalize_text_content_block(value)]


def text_from_content_blocks(blocks: TextMessageContentBlocks) -> str:
    """Return the concatenated text portion of typed content blocks."""
    text_parts = [block.text for block in blocks if isinstance(block, TextContent)]
    return " ".join(text_parts)


def content_block_to_platform_dict(block: TextMessageContentBlock) -> Dict[str, Any]:
    """Serialize a content block to the platform block-array wire shape."""
    return block.model_dump(mode="json", exclude_none=True)


def _normalize_text_content_block(value: Any) -> TextMessageContentBlock:
    if isinstance(value, TextContent | ImageUrlContent):
        return value

    if isinstance(value, str):
        return TextContent(text=value)

    if isinstance(value, dict):
        if "type" in value:
            if value["type"] == TEXT_CONTENT_TYPE:
                return TextContent.model_validate(value)
            if value["type"] == IMAGE_URL_CONTENT_TYPE:
                return ImageUrlContent.model_validate(value)
            raise ValueError(f"Unsupported content block type: {value['type']}")

        if "text" in value:
            return TextContent(text=str(value["text"]))

        if "image_url" in value:
            return ImageUrlContent.model_validate(
                {"type": IMAGE_URL_CONTENT_TYPE, "image_url": value["image_url"]}
            )

        if "url" in value:
            return ImageUrlContent(image_url=ImageUrlPayload(url=str(value["url"])))

    raise ValueError(f"Unsupported text message content block: {type(value)}")


class ToolUseContent(BaseModel):
    """Tool use content - represents a request to execute a tool.

    This is stored when an LLM requests to use a tool.
    Database format for TOOL_USE messages.
    """

    type: Literal["tool_use"] = TOOL_USE_CONTENT_TYPE
    id: str = Field(..., description="Unique identifier for this tool use")
    name: str = Field(..., description="Name of the tool to execute")
    input: Dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the tool"
    )


class ToolResultContent(BaseModel):
    """Tool result content - represents the result of tool execution.

    This is stored when a tool execution completes.
    Database format for TOOL_RESULT messages.
    """

    type: Literal["tool_result"] = TOOL_RESULT_CONTENT_TYPE
    tool_use_id: str = Field(
        ..., description="ID of the tool use this result corresponds to"
    )
    content: Any = Field(
        ..., description="Tool execution result - can be string, dict, list, etc."
    )
    name: Optional[str] = Field(None, description="Name of the tool that was executed")
    is_error: bool = Field(default=False, description="Whether execution failed")


class UserMessageContent(BaseModel):
    """Content structure for USER messages in database.

    Database format: {"role": "user", "content": [{"type": "text", ...}, ...]}
    """

    role: Literal["user"] = USER_ROLE
    content: TextMessageContentBlocks = Field(..., description="Message content blocks")

    @field_validator("content", mode="before")
    @classmethod
    def validate_content_blocks(cls, value: Any) -> TextMessageContentBlocks:
        return normalize_text_content_blocks(value)

    def get_text_content(self) -> str:
        return text_from_content_blocks(self.content)

    def to_html_content(self) -> str:
        return md_to_html(self.get_text_content())


class AssistantMessageContent(BaseModel):
    """Content structure for ASSISTANT messages in database.

    Database format: {"role": "assistant", "content": [{"type": "text", ...}, ...]}
    """

    role: Literal["assistant"] = ASSISTANT_ROLE
    content: TextMessageContentBlocks = Field(
        ..., description="Assistant message blocks"
    )

    @field_validator("content", mode="before")
    @classmethod
    def validate_content_blocks(cls, value: Any) -> TextMessageContentBlocks:
        return normalize_text_content_blocks(value)

    def get_text_content(self) -> str:
        return text_from_content_blocks(self.content)

    def to_html_content(self) -> str:
        return md_to_html(self.get_text_content())


class ToolUseMessageContent(BaseModel):
    """Content structure for TOOL_USE messages in database.

    Database format: {"role": "tool_use", "content": {...}}
    """

    role: Literal["tool_use"] = TOOL_USE_ROLE
    content: ToolUseContent = Field(..., description="Tool use details")

    def get_text_content(self) -> str:
        return f"Tool Use: {self.content.name}"

    def to_html_content(self) -> str:
        formatted_json = json.dumps(self.content.model_dump(), indent=2)
        return formatted_json


class ToolResultMessageContent(BaseModel):
    """Content structure for TOOL_RESULT messages in database.

    Database format: {"role": "user", "content": [{...}]}
    """

    role: Literal["user"] = USER_ROLE
    content: List[ToolResultContent] = Field(
        ..., description="List of tool results (usually one)"
    )

    def get_text_content(self) -> str:
        content_ = ""
        results = self.content
        for result in results:
            if isinstance(result.content, str):
                content_ += result.content
                content_ += "\n"
            else:
                content_ += str(result.content)
                content_ += "\n"
        return content_.strip()

    def to_html_content(self) -> str:
        results_json = [result.model_dump() for result in self.content]
        formatted_json = json.dumps(results_json, indent=2)
        return formatted_json


class SystemMessageContent(BaseModel):
    role: Literal["system"] = SYSTEM_ROLE
    content: TextMessageContentBlocks = Field(..., description="System message blocks")

    @field_validator("content", mode="before")
    @classmethod
    def validate_content_blocks(cls, value: Any) -> TextMessageContentBlocks:
        return normalize_text_content_blocks(value)

    def get_text_content(self) -> str:
        return text_from_content_blocks(self.content)

    def to_html_content(self) -> str:
        return md_to_html(self.get_text_content())


class WidgetPayload(BaseModel):
    """Validated single-component widget payload envelope."""

    component: str = Field(..., description="Registered widget component type")
    props: Dict[str, Any] = Field(
        default_factory=dict, description="Component props validated by the backend"
    )


class CompoundWidgetPayload(BaseModel):
    """Validated compound widget payload — flat adjacency list of components."""

    components: List[Dict[str, Any]] = Field(
        ..., description="Flat list of component nodes"
    )
    root: str = Field(..., description="ID of the root component")


class WidgetMessageContent(BaseModel):
    """Content structure for ASSISTANT widget messages (single or compound).

    Both single-component and compound payloads use contentKind=WIDGET.
    The widget SDK detects the format by checking for `component` (single)
    vs `components`+`root` (compound) keys in the payload.
    """

    role: Literal["assistant"] = "assistant"
    content: Union[WidgetPayload, CompoundWidgetPayload] = Field(
        ..., description="Widget payload — single component or compound layout"
    )

    def get_text_content(self) -> str:
        if isinstance(self.content, WidgetPayload):
            return (
                "Interactive widget rendered for the user.\n"
                f"Component: {self.content.component}\n"
                "Props:\n"
                f"{_to_pretty_json(self.content.props)}"
            )
        # Compound payload
        component_ids = [c.get("id", "?") for c in self.content.components]
        component_types = [c.get("component", "?") for c in self.content.components]
        return (
            "Compound interactive widget rendered for the user.\n"
            f"Root: {self.content.root}\n"
            f"Components ({len(self.content.components)}): "
            f"{', '.join(f'{cid}({ct})' for cid, ct in zip(component_ids, component_types))}\n"
            "Full payload:\n"
            f"{_to_pretty_json(self.content.model_dump())}"
        )

    def to_html_content(self) -> str:
        return ""


_WIDGET_COMPONENT_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_WIDGET_DATA_MAX_BYTES = 64 * 1024  # 64 KB


class WidgetResponseData(BaseModel):
    """Structured widget submission payload from the user."""

    type: Literal["widget_response"] = "widget_response"
    widget_message_id: str = Field(
        ..., description="ID of the widget message this response belongs to"
    )
    component: str = Field(..., description="Component type that emitted the response")
    action: Optional[str] = Field(
        None, description="Interaction verb such as submit or select"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Structured widget submission data"
    )

    @field_validator("component")
    @classmethod
    def validate_component_name(cls, v: str) -> str:
        if not _WIDGET_COMPONENT_RE.match(v):
            raise ValueError(
                "component must be lowercase alphanumeric with underscores, max 64 chars"
            )
        return v

    @model_validator(mode="after")
    def validate_data_size(self) -> "WidgetResponseData":
        raw = json.dumps(self.data, default=str)
        if len(raw.encode("utf-8")) > _WIDGET_DATA_MAX_BYTES:
            raise ValueError("widget response data exceeds maximum allowed size")
        return self


class WidgetResponseMessageContent(BaseModel):
    """Content structure for USER widget response messages."""

    role: Literal["user"] = "user"
    content: WidgetResponseData = Field(..., description="Structured widget response")

    def get_text_content(self) -> str:
        action_line = f"Action: {self.content.action}\n" if self.content.action else ""
        return (
            "User submitted a widget response.\n"
            f"Widget Message ID: {self.content.widget_message_id}\n"
            f"Component: {self.content.component}\n"
            f"{action_line}"
            "Submitted Data:\n"
            f"{_to_pretty_json(self.content.data)}"
        )

    def to_html_content(self) -> str:
        return ""


def normalize_widget_response_message_content(
    content: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize raw or wrapped widget-response payloads to platform-native shape."""
    if content.get("role") == "user" and isinstance(content.get("content"), dict):
        return WidgetResponseMessageContent.model_validate(content).model_dump()

    normalized_content = WidgetResponseData.model_validate(content)
    return WidgetResponseMessageContent(
        role="user",
        content=normalized_content,
    ).model_dump()


# ====================== Content Block Union Type ======================

# Discriminated union of all content block types
# Similar to Anthropic's ContentBlock type
ContentBlock = Annotated[
    Union[TextContent, ImageUrlContent, ToolUseContent, ToolResultContent],
    Field(discriminator="type"),
]
