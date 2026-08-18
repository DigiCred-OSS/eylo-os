"""Conversation-domain inputs received through the WebSocket adapter."""

from typing import Optional
from uuid import UUID

from pydantic import Field, model_validator

from eylo.common.contracts.websocket import WsConversationQueryFilters, WsEvent
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageRequestFeedback,
)


class WsMessageEvent(WsEvent):
    """Message event for sending text or data."""

    conversation_id: UUID
    content_kind: MessageContentKind = MessageContentKind.TEXT
    text: Optional[str] = None
    content: Optional[dict | list[dict]] = None
    parent_message_id: Optional[UUID] = None
    context: Optional[dict] = None

    @model_validator(mode="after")
    def validate_payload(self) -> "WsMessageEvent":
        if self.content_kind == MessageContentKind.TEXT:
            if self.text and self.text.strip():
                if self.content is not None:
                    raise ValueError("content must not be provided for TEXT messages")
                return self
            raise ValueError("text is required for TEXT messages")

        if self.content_kind == MessageContentKind.WIDGET_RESPONSE:
            if self.content is None:
                raise ValueError("content is required for WIDGET_RESPONSE messages")
            if not isinstance(self.content, dict):
                raise ValueError(
                    "content must be an object for WIDGET_RESPONSE messages"
                )
            return self

        raise ValueError(
            f"Unsupported websocket message content kind: {self.content_kind}"
        )


class WsMessageFeedbackEvent(WsEvent):
    conversation_id: UUID
    message_request_id: UUID
    request_feedback: MessageRequestFeedback


class WsMessagesQueryFilters(WsConversationQueryFilters):
    """Filters for querying conversations."""

    message_ids: list[UUID] = Field(default_factory=list)


class WsMessageQueryEvent(WsEvent):
    """Event to query messages in a conversation."""

    filters: WsMessagesQueryFilters = Field(default_factory=WsMessagesQueryFilters)
