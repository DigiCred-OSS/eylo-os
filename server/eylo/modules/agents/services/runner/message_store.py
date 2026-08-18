"""Shared message persistence helpers.

Framework-facing adapters call these helpers directly because they need return
values (message IDs) for the parent-message chain.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

import arrow

from eylo.common.contracts.llm_response import LLMContentType
from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_RUNTIME_MODE,
    VOICE_MESSAGE_META_SESSION_ID,
    VOICE_MESSAGE_META_SESSION_ROW_ID,
)
from eylo.common.database import get_transaction
from eylo.modules.conversations.schemas.message_content import (
    AssistantMessageContent,
    TextContent,
    ToolResultContent,
    ToolResultMessageContent,
    ToolUseContent,
    ToolUseMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageKind,
    RequestStatus,
)
from eylo.modules.conversations.services.messages import MessageService

if TYPE_CHECKING:
    from eylo.common.contracts.llm_response import LLMResponse, LLMToolUseBlock
    from eylo.modules.conversations.schemas.messages import MessageInDb

logger = logging.getLogger(__name__)


# ── User-facing error messages ──


class ErrorMessages:
    """User-facing error messages for different failure scenarios."""

    EMPTY_RESPONSE = (
        "I apologize, but I encountered an issue generating a response. "
        "Could you please rephrase your request?"
    )
    MAX_ITERATIONS = (
        "I apologize, but I'm having trouble completing this request. "
        "Could you please try rephrasing or breaking it into smaller steps?"
    )
    TOOL_PARSE_ERROR = (
        "Error: Failed to parse tool request. Please retry with valid tool parameters."
    )
    REQUEST_TIMEOUT = (
        "I apologize, but this request is taking too long to process. "
        "Please try again with a simpler request."
    )
    GENERIC_ERROR = (
        "I apologize, but I encountered an error while processing your request. "
        "Please try again."
    )
    CIRCUIT_BREAKER = "I apologize, but could you please verify your request?\n{}"


class MessageStore:
    """Persists messages generated during an agent run."""

    def __init__(self) -> None:
        self.message_service = MessageService()

    async def store_llm_response(
        self,
        run_ctx: Any,
        llm_response: LLMResponse,
        parent_message_id: UUID,
    ) -> List[MessageInDb]:
        """Parse an LLM response into messages and persist them.

        Creates ASSISTANT messages for text content blocks and TOOL_USE
        messages for tool_use content blocks.

        Returns all created messages. The last message's ID should be
        used as parent_message_id for subsequent messages.
        """
        ctx = run_ctx.conversation_context
        agent_participant = ctx.get_primary_agent()
        request_id = run_ctx.user_message.request_id if run_ctx.user_message else None

        created_messages: List[MessageInDb] = []
        request_status = RequestStatus.PROCESSING
        voice_meta = _voice_message_meta(run_ctx)

        for content in llm_response.content:
            content_type = LLMContentType(content.type)

            if content_type == LLMContentType.TEXT:
                # Status stays PROCESSING — hooks manage the COMPLETED transition
                message_content = AssistantMessageContent(
                    role=MessageKind.ASSISTANT.value.lower(),
                    content=TextContent(type="text", text=content.content.text),
                )
                message = await self.message_service.create_(
                    MessageCreate(
                        conversation_id=ctx.conversation.id,
                        sender_participant_id=agent_participant.id,
                        kind=MessageKind.ASSISTANT,
                        content_kind=MessageContentKind.TEXT,
                        content=message_content,
                        external_id=llm_response.id,
                        meta={**llm_response.model_dump(), **voice_meta},
                        created_at=arrow.utcnow().datetime,
                        parent_message_id=parent_message_id,
                        request_id=request_id,
                        request_status=request_status,
                    )
                )
                created_messages.append(message)

            elif content_type == LLMContentType.TOOL_USE:
                request_status = RequestStatus.AWAITING_TOOL_RESULTS
                external_id = content.content.id or content.id or llm_response.id
                message_content = ToolUseMessageContent(
                    role=MessageKind.TOOL_USE.value.lower(),
                    content=ToolUseContent(
                        id=external_id,
                        type=MessageKind.TOOL_USE.value.lower(),
                        name=content.content.name,
                        input=content.content.input,
                    ),
                )
                message = await self.message_service.create_(
                    MessageCreate(
                        conversation_id=ctx.conversation.id,
                        sender_participant_id=agent_participant.id,
                        kind=MessageKind.TOOL_USE,
                        content_kind=MessageContentKind.TOOL,
                        content=message_content,
                        external_id=external_id,
                        meta={**llm_response.model_dump(), **voice_meta},
                        created_at=arrow.utcnow().datetime,
                        parent_message_id=parent_message_id,
                        request_id=request_id,
                        request_status=request_status,
                    )
                )
                created_messages.append(message)
            else:
                logger.warning(f"Unsupported content type: {content_type}")

        await get_transaction().commit()
        return created_messages

    async def store_tool_result(
        self,
        run_ctx: Any,
        tool_use_message: MessageInDb,
        tool_use_block: LLMToolUseBlock,
        tool_result: str,
        sender_id: UUID,
        meta: Optional[dict] = None,
        is_error: bool = False,
    ) -> MessageInDb:
        """Persist a tool execution result as a TOOL_RESULT message."""
        message = await self.message_service.create_(
            MessageCreate(
                conversation_id=tool_use_message.conversation_id,
                sender_participant_id=sender_id,
                kind=MessageKind.TOOL_RESULT,
                content_kind=MessageContentKind.TOOL,
                content=ToolResultMessageContent(
                    role=MessageKind.USER.value.lower(),
                    content=[
                        ToolResultContent(
                            type=MessageKind.TOOL_RESULT.value.lower(),
                            tool_use_id=tool_use_message.external_id,
                            name=tool_use_block.name,
                            content=tool_result,
                            is_error=is_error,
                        )
                    ],
                ),
                meta=meta or {},
                created_at=arrow.utcnow().datetime,
                parent_message_id=tool_use_message.id,
                request_id=tool_use_message.request_id,
                request_status=RequestStatus.PROCESSING,
            )
        )
        await get_transaction().commit()
        return message

    async def store_tool_error(
        self,
        tool_use_message: MessageInDb,
        error_message: str,
    ) -> MessageInDb:
        """Store a tool parse/execution error so the LLM can retry."""
        message = await self.message_service.create_(
            MessageCreate(
                conversation_id=tool_use_message.conversation_id,
                sender_participant_id=tool_use_message.sender_participant_id,
                kind=MessageKind.TOOL_RESULT,
                content_kind=MessageContentKind.TOOL,
                content=ToolResultMessageContent(
                    role=MessageKind.USER.value.lower(),
                    content=[
                        ToolResultContent(
                            type=MessageKind.TOOL_RESULT.value.lower(),
                            tool_use_id=tool_use_message.external_id,
                            name="error",
                            content=error_message,
                            is_error=True,
                        )
                    ],
                ),
                meta=_build_error_metadata(Exception("Tool parsing failed")),
                created_at=arrow.utcnow().datetime,
                parent_message_id=tool_use_message.id,
                request_id=tool_use_message.request_id,
                request_status=RequestStatus.PROCESSING,
            )
        )
        await get_transaction().commit()
        return message

    async def store_error_message(
        self,
        run_ctx: Any,
        error_text: str,
        parent_message_id: UUID,
        request_status: RequestStatus = RequestStatus.FAILED,
    ) -> MessageInDb:
        """Persist a user-facing error message as an ASSISTANT message."""
        ctx = run_ctx.conversation_context
        agent_participant = ctx.get_primary_agent()
        request_id = run_ctx.user_message.request_id if run_ctx.user_message else None

        message = await self.message_service.create_(
            MessageCreate(
                conversation_id=ctx.conversation.id,
                sender_participant_id=agent_participant.id,
                kind=MessageKind.ASSISTANT,
                content_kind=MessageContentKind.TEXT,
                content=AssistantMessageContent(
                    role=MessageKind.ASSISTANT.value.lower(),
                    content=TextContent(type="text", text=error_text),
                ),
                meta={
                    **_build_error_metadata(Exception(error_text)),
                    **_voice_message_meta(run_ctx),
                },
                created_at=arrow.utcnow().datetime,
                parent_message_id=parent_message_id,
                request_id=request_id,
                request_status=request_status,
            )
        )
        await get_transaction().commit()
        return message

    async def store_assistant_message(
        self,
        run_ctx: Any,
        text: str,
        parent_message_id: UUID,
        meta: Optional[dict] = None,
        request_status: RequestStatus = RequestStatus.COMPLETED,
        sender_participant_id: Optional[UUID] = None,
    ) -> MessageInDb:
        """Persist a generic ASSISTANT message (circuit breaker, empty, etc.)."""
        ctx = run_ctx.conversation_context
        agent_participant = ctx.get_primary_agent()
        request_id = run_ctx.user_message.request_id if run_ctx.user_message else None

        message = await self.message_service.create_(
            MessageCreate(
                conversation_id=ctx.conversation.id,
                sender_participant_id=sender_participant_id or agent_participant.id,
                kind=MessageKind.ASSISTANT,
                content_kind=MessageContentKind.TEXT,
                content=AssistantMessageContent(
                    role=MessageKind.ASSISTANT.value.lower(),
                    content=TextContent(type="text", text=text),
                ),
                meta={**(meta or {}), **_voice_message_meta(run_ctx)},
                created_at=arrow.utcnow().datetime,
                parent_message_id=parent_message_id,
                request_id=request_id,
                request_status=request_status,
            )
        )
        await get_transaction().commit()
        return message

    async def update_request_status(
        self,
        request_id: UUID,
        status: RequestStatus,
        conversation_id: UUID,
    ) -> None:
        """Update the request status for a given request_id and commit."""
        await self.message_service.update_request_status_by_request_id(
            request_id,
            status,
            conversation_id=conversation_id,
        )
        await get_transaction().commit()


# ── Helpers ──


def _build_error_metadata(error: Exception) -> dict:
    return {
        "error": True,
        "error_type": error.__class__.__name__,
        "error_message": str(error),
    }


def _voice_message_meta(run_ctx: Any) -> dict[str, Any]:
    message = getattr(run_ctx, "user_message", None)
    raw = getattr(message, "meta", None)
    if raw is None:
        return {}
    source = raw if isinstance(raw, dict) else raw.model_dump(exclude_none=True)
    keys = (
        VOICE_MESSAGE_META_SESSION_ROW_ID,
        VOICE_MESSAGE_META_SESSION_ID,
        VOICE_MESSAGE_META_RUNTIME_MODE,
    )
    return {key: source[key] for key in keys if source.get(key) is not None}


def format_widget_render_fallback() -> str:
    """Return a model-safe fallback without reflecting tool or exception text."""
    return (
        "A widget could not be rendered. Do not call another widget tool "
        "during this turn. Reply to the user in normal plain text instead."
    )
