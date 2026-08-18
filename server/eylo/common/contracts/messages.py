"""Provider-neutral message content contracts."""

import datetime
from enum import Enum
from typing import Any, List, Optional, Self, TypeAlias, TypeVar, Union
from uuid import UUID
import logging
from pydantic import ConfigDict, field_validator, model_validator


logger = logging.getLogger(__name__)

MessageEnumT = TypeVar("MessageEnumT", bound=Enum)
from eylo.common.schemas import (
    CaseInSensitiveEnum,
    EyloBaseModelSchema,
    EyloBaseResponseSchema,
    EyloBaseSchema,
    PaginatedResponseSchema,
)
from eylo.common.contracts.message_content import (
    AssistantMessageContent,
    SystemMessageContent,
    TextContent,
    ToolResultMessageContent,
    ToolUseMessageContent,
    UserMessageContent,
    WidgetMessageContent,
    WidgetResponseMessageContent,
)

MessageContentType: TypeAlias = Union[
    UserMessageContent,
    AssistantMessageContent,
    ToolUseMessageContent,
    ToolResultMessageContent,
    SystemMessageContent,
    WidgetMessageContent,
    WidgetResponseMessageContent,
]


# ====================== Enums ======================


class MessageKind(CaseInSensitiveEnum):
    """Enum for message categories."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL_RESULT = "TOOL_RESULT"
    TOOL_USE = "TOOL_USE"


class MessageContentKind(str, Enum):
    """Enum for message content types."""

    TEXT = "TEXT"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    TOOL = "TOOL"
    WIDGET = "WIDGET"
    WIDGET_RESPONSE = "WIDGET_RESPONSE"
    # System Content that summarizes the llm messages
    SUMMARY = "SUMMARY"
    # Background task dispatched by spawn_task_fnf tool
    TASK = "TASK"
    # Result produced by a completed background task
    TASK_RESULT = "TASK_RESULT"


class RequestStatus(CaseInSensitiveEnum):
    """Enum for message request lifecycle status.

    Lifecycle flow:
    - PENDING → PROCESSING → AWAITING_TOOL_RESULTS → PROCESSING → COMPLETED
    - PENDING/PROCESSING → INTERRUPTED (when new user message arrives)
    - Any state → FAILED (on error)

    INTERRUPTED status indicates the request was superseded by a newer request
    and should be ignored in LLM context and TTS output.

    SKIPPED indicates the worker picked the task up and decided no work was
    needed. Like INTERRUPTED it should be ignored in LLM context and TTS
    output, but it is not a failure and not a supersession.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AWAITING_TOOL_RESULTS = "AWAITING_TOOL_RESULTS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"  # Request superseded by newer user message
    # Decided by the agent that picked the work up, not by the queue: it looked
    # and found nothing to do. A redundant title regeneration is not an error
    # and must not read as one. Distinct from INTERRUPTED, which is the queue's
    # judgement that a newer request superseded this one.
    SKIPPED = "SKIPPED"


class MessageRequestFeedback(CaseInSensitiveEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class MessageMeta(EyloBaseSchema):
    """Extensible metadata envelope for persisted messages.

    Message producers own the specific meta schema for their subsystem. The
    conversation module validates that meta is object-shaped while allowing
    producer-owned fields to evolve without coupling conversations to agents,
    sockets, widgets, or integrations.
    """

    model_config = ConfigDict(extra="allow")

    def get(self, key: str, default: Any = None) -> Any:
        """Return producer-owned meta value while preserving dict-like callers."""
        return self.model_extra.get(key, default) if self.model_extra else default

    def __contains__(self, key: str) -> bool:
        return bool(self.model_extra and key in self.model_extra)

    def __getitem__(self, key: str) -> Any:
        if key not in self:
            raise KeyError(key)
        return self.model_extra[key]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (self.model_extra or {}) == other
        return super().__eq__(other)


def _coerce_known_enum(
    value: Any, enum_type: type[MessageEnumT]
) -> MessageEnumT | None:
    """Coerce persisted enum values into strict schema enum members."""
    if value is None:
        return None

    candidate = value if isinstance(value, enum_type) else enum_type(value)
    if candidate not in tuple(enum_type):
        raise ValueError(f"{value!r} is not a valid {enum_type.__name__}")

    return candidate


# ====================== Message Schemas ======================


class MessageModelSchema(EyloBaseModelSchema):
    conversation_id: UUID
    user_session_id: UUID | None = None
    sender_participant_id: UUID
    agent_run_id: UUID | None = None
    kind: MessageKind = MessageKind.USER
    content_kind: MessageContentKind = MessageContentKind.TEXT

    # Typed message content - platform-native schemas
    # Always stored as one of the typed content schemas for type safety
    content: Optional[MessageContentType] = None

    parent_message_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    request_status: Optional["RequestStatus"] = None
    request_feedback: Optional["MessageRequestFeedback"] = None
    meta: Optional[MessageMeta] = None
    external_id: Optional[str] = None

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, v: Any) -> MessageKind:
        return _coerce_known_enum(v, MessageKind)

    @field_validator("content_kind", mode="before")
    @classmethod
    def validate_content_kind(cls, v: Any) -> MessageContentKind:
        return _coerce_known_enum(v, MessageContentKind)

    @field_validator("request_status", mode="before")
    @classmethod
    def validate_request_status(cls, v: Any) -> RequestStatus | None:
        return _coerce_known_enum(v, RequestStatus)

    @field_validator("request_feedback", mode="before")
    @classmethod
    def validate_request_feedback(cls, v: Any) -> MessageRequestFeedback | None:
        return _coerce_known_enum(v, MessageRequestFeedback)

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v, info):
        """Convert dict to typed message content automatically.

        This ensures database values (dicts) are always converted to
        proper Pydantic schemas on load, maintaining type safety.
        """
        if v is None or not isinstance(v, dict):
            return v

        content_kind = info.data.get("content_kind")
        kind = info.data.get("kind")

        # Convert persisted JSON to the exact typed schema. Invalid rows fail at
        # the read boundary instead of leaking untyped dicts into the runtime.
        if content_kind == MessageContentKind.WIDGET:
            return WidgetMessageContent.model_validate(v)
        if content_kind == MessageContentKind.WIDGET_RESPONSE:
            return WidgetResponseMessageContent.model_validate(v)
        if kind == MessageKind.USER:
            return UserMessageContent.model_validate(v)
        if kind == MessageKind.ASSISTANT:
            return AssistantMessageContent.model_validate(v)
        if kind == MessageKind.TOOL_USE:
            return ToolUseMessageContent.model_validate(v)
        if kind == MessageKind.TOOL_RESULT:
            return ToolResultMessageContent.model_validate(v)
        if kind == MessageKind.SYSTEM:
            return SystemMessageContent.model_validate(v)
        raise ValueError("Message content requires a supported message kind.")


class MessageCreate(EyloBaseSchema):
    conversation_id: UUID
    user_session_id: UUID | None = None
    sender_participant_id: UUID
    agent_run_id: UUID | None = None
    created_at: datetime.datetime
    kind: MessageKind = MessageKind.USER
    content_kind: MessageContentKind = MessageContentKind.TEXT

    # Typed message content - same as MessageModelSchema
    content: Optional[MessageContentType] = None

    parent_message_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    request_status: Optional["RequestStatus"] = None
    meta: Optional[MessageMeta] = None
    external_id: Optional[str] = None

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, v: Any) -> MessageKind:
        return _coerce_known_enum(v, MessageKind)

    @field_validator("content_kind", mode="before")
    @classmethod
    def validate_content_kind(cls, v: Any) -> MessageContentKind:
        return _coerce_known_enum(v, MessageContentKind)

    @field_validator("request_status", mode="before")
    @classmethod
    def validate_request_status(cls, v: Any) -> RequestStatus | None:
        return _coerce_known_enum(v, RequestStatus)

class MessageInDb(MessageModelSchema):
    model_config = ConfigDict(from_attributes=True)

    def get_parsed_content(self):
        """Parse and validate message content based on message kind.

        Returns a Pydantic model instance for the content, providing type safety
        and validation. This helps catch schema mismatches early.

        Returns:
            UserMessageContent | AssistantMessageContent | ToolUseMessageContent | ToolResultMessageContent

        Raises:
            ValueError: If content doesn't match expected schema for message kind

        Example:
            >>> msg = MessageInDb(kind=MessageKind.TOOL_USE, content={...})
            >>> content = msg.get_parsed_content()
            >>> print(content.content.id)  # Type-safe access!
            >>> print(content.content.name)

        """
        if not self.content:
            raise ValueError(f"Message {self.id} has no content")

        try:
            if self.content_kind == MessageContentKind.WIDGET:
                return WidgetMessageContent.model_validate(self.content)
            elif self.content_kind == MessageContentKind.WIDGET_RESPONSE:
                return WidgetResponseMessageContent.model_validate(self.content)
            elif self.kind == MessageKind.USER:
                return UserMessageContent.model_validate(self.content)
            elif self.kind == MessageKind.ASSISTANT:
                return AssistantMessageContent.model_validate(self.content)
            elif self.kind == MessageKind.TOOL_USE:
                return ToolUseMessageContent.model_validate(self.content)
            elif self.kind == MessageKind.TOOL_RESULT:
                return ToolResultMessageContent.model_validate(self.content)
            elif self.kind == MessageKind.SYSTEM:
                return SystemMessageContent.model_validate(self.content)
            else:
                raise ValueError(f"Unknown message kind: {self.kind}")
        except Exception as error:
            raise ValueError(f"Failed to parse {self.kind} message content.") from error

    def get_tool_use_content(self):
        """Get parsed tool use content with type safety.

        Returns:
            ToolUseMessageContent with validated ToolUseContent

        Raises:
            ValueError: If message is not TOOL_USE or content is invalid

        """
        if self.kind != MessageKind.TOOL_USE:
            raise ValueError(f"Message {self.id} is {self.kind}, not TOOL_USE")

        parsed = self.get_parsed_content()
        if not isinstance(parsed, ToolUseMessageContent):
            raise ValueError(f"Expected ToolUseMessageContent, got {type(parsed)}")

        return parsed

    def get_tool_result_content(self):
        """Get parsed tool result content with type safety.

        Returns:
            ToolResultMessageContent with validated List[ToolResultContent]

        Raises:
            ValueError: If message is not TOOL_RESULT or content is invalid

        """
        if self.kind != MessageKind.TOOL_RESULT:
            raise ValueError(f"Message {self.id} is {self.kind}, not TOOL_RESULT")

        parsed = self.get_parsed_content()
        if not isinstance(parsed, ToolResultMessageContent):
            raise ValueError(f"Expected ToolResultMessageContent, got {type(parsed)}")

        return parsed

    def get_text_content(self) -> Optional[str]:
        """Extract text content from any message type.

        Handles all message content types and extracts displayable text:
        - USER: Direct text or concatenated text blocks
        - ASSISTANT: Extracted text from TextContent or dict
        - TOOL_USE: Tool name and formatted input
        - TOOL_RESULT: Formatted tool results

        Returns:
            Optional[str]: Extracted text content, or None if no content

        Example:
            >>> msg = MessageInDb(kind=MessageKind.USER, content={"role": "user", "content": "Hello"})
            >>> msg.get_text_content()
            "Hello"

            >>> msg = MessageInDb(kind=MessageKind.ASSISTANT, content={"role": "assistant", "content": {"type": "text", "text": "Hi there"}})
            >>> msg.get_text_content()
            "Hi there"

        """
        if not self.content:
            return None

        try:
            parsed_content = self.get_parsed_content()

            # USER messages
            if isinstance(parsed_content, UserMessageContent):
                return parsed_content.get_text_content()

            # ASSISTANT messages
            elif isinstance(parsed_content, AssistantMessageContent):
                return parsed_content.get_text_content()

            # TOOL_USE messages
            elif isinstance(parsed_content, ToolUseMessageContent):
                return parsed_content.get_text_content()

            # TOOL_RESULT messages
            elif isinstance(parsed_content, ToolResultMessageContent):
                return parsed_content.get_text_content()

            elif isinstance(parsed_content, SystemMessageContent):
                return parsed_content.get_text_content()

            elif isinstance(parsed_content, WidgetMessageContent):
                return parsed_content.get_text_content()

            elif isinstance(parsed_content, WidgetResponseMessageContent):
                return parsed_content.get_text_content()

            return None

        except Exception:
            # Fallback: return None if parsing fails
            return None


# ====================== Response Models ======================
# flake8: noqa E501


class MessageApiResponseSchema(MessageInDb, EyloBaseResponseSchema):
    html_content: Optional[str] = None

    @model_validator(mode="after")
    def set_html_content(self) -> Self:
        """Generate HTML content from markdown content."""
        if self.content is not None:
            self.html_content = self.content.to_html_content()
        return self


class ConversationMessagesPaginated(PaginatedResponseSchema):
    """Paginated list of messages for a conversation."""

    data: List[MessageApiResponseSchema]
