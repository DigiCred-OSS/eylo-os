"""Registered compound-widget rendering system tool."""

import logging
from typing import Any

import arrow
from pydantic import BaseModel, Field, ValidationError

from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.message_content import (
    CompoundWidgetPayload,
    WidgetMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageKind,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.interfaces.schemas.api import (
    ALL_COMPOUND_COMPONENT_TYPES,
    COMPOUND_MAX_COMPONENTS,
)
from eylo.modules.interfaces.services.schema_validator import (
    CompoundWidgetSchemaValidatorService,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema model exposed to the LLM via __eylo_schema_model__
# ---------------------------------------------------------------------------


class CompoundComponentNode(BaseModel):
    id: str = Field(..., description="Unique identifier for this component.")
    component: str = Field(
        ...,
        description="Component type.",
        json_schema_extra={"enum": ALL_COMPOUND_COMPONENT_TYPES},
    )
    props: str = Field(
        default="{}",
        description=(
            "JSON-serialized object of component-specific properties. "
            "Must be a valid JSON object string."
        ),
    )
    children: list[str] | None = Field(
        default=None,
        description="Ordered child component IDs (layout components only).",
    )


class CompoundRenderWidgetInput(BaseModel):
    """Pydantic model used as the compound tool's input_schema.

    The description is overridden at registration time with the full
    catalog description compiled by CompoundWidgetSchemaValidatorService.
    """

    components: list[CompoundComponentNode] = Field(
        ...,
        min_length=1,
        max_length=COMPOUND_MAX_COMPONENTS,
        description="Flat list of component nodes with ID-based relationships.",
    )
    root: str = Field(
        ...,
        description="ID of the root component.",
    )

    class Config:
        json_schema_extra = {
            "additionalProperties": False,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_log_context(
    raw: dict[str, Any],
    ctx: ConversationContext,
) -> dict[str, Any]:
    """Build compact, non-sensitive context for compound_render_widget logs."""
    latest_user_message = next(
        (
            message
            for message in reversed(ctx.messages or [])
            if message.kind == MessageKind.USER
        ),
        None,
    )
    components = raw.get("components", [])
    return {
        "conversation_id": str(ctx.conversation.id),
        "request_id": str(latest_user_message.request_id)
        if latest_user_message
        else None,
        "component_count": len(components),
        "widget_interfaces_enabled": ctx.widget_interfaces_enabled,
    }


_build_log_context.__eylo_hidden__ = True  # type: ignore[attr-defined]


def _build_text_fallback_result(reason: str) -> str:
    """Tell the model to stop retrying and answer in text."""
    return (
        "Compound widget rendering could not be completed. "
        f"Reason: {reason} "
        "Do not call `compound_render_widget` again for this turn. "
        "Reply to the user in normal plain text instead."
    )


_build_text_fallback_result.__eylo_hidden__ = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# compound_render_widget tool
# ---------------------------------------------------------------------------


async def compound_render_widget(
    components: list[dict[str, Any]],
    root: str,
    ctx: ConversationContext,
) -> str:
    """Render a compound layout of UI components in the user's chat widget.

    Use for both collecting structured input (forms, selections) and
    presenting information (tables, cards, alerts, progress, text) in
    a visually rich, organized manner.
    """
    raw = {"components": components, "root": root}
    log_context = _build_log_context(raw=raw, ctx=ctx)
    logger.info("compound_render_widget invoked: %s", log_context)

    if not ctx.widget_interfaces_enabled:
        logger.warning(
            "compound_render_widget called outside widget/browser conversation: %s",
            log_context,
        )
        return _build_text_fallback_result(
            "Interactive widgets are unavailable in this conversation.",
        )

    validator = CompoundWidgetSchemaValidatorService()
    try:
        validated_payload = validator.validate_compound_payload(raw)
        logger.info(
            "compound_render_widget payload validated: %s",
            {
                **log_context,
                "validated_root": validated_payload.root,
                "validated_count": len(validated_payload.components),
            },
        )
    except (ValueError, TypeError, ValidationError) as error:
        logger.warning(
            "compound_render_widget validation failed context=%s error_type=%s",
            log_context,
            type(error).__name__,
        )
        # This textual fallback is currently classified by the execution layer
        # as a successful tool result rather than a transport failure.
        return _build_text_fallback_result(
            "Widget input was invalid. Reply in plain text instead."
        )

    agent_participant = ctx.get_primary_agent()
    if agent_participant is None:
        logger.warning(
            "compound_render_widget missing primary agent participant: %s",
            log_context,
        )
        return _build_text_fallback_result(
            "No primary agent participant is available for widget delivery.",
        )

    latest_user_message = next(
        (
            message
            for message in reversed(ctx.messages or [])
            if message.kind == MessageKind.USER
        ),
        None,
    )

    # Serialize validated nodes to dicts for storage
    serialized_components = [
        node.model_dump(exclude_none=True, by_alias=True)
        for node in validated_payload.components
    ]

    widget_content = WidgetMessageContent(
        role="assistant",
        content=CompoundWidgetPayload(
            components=serialized_components,
            root=validated_payload.root,
        ),
    )

    widget_message = await MessageService().create_(
        MessageCreate(
            conversation_id=ctx.conversation.id,
            sender_participant_id=agent_participant.id,
            kind=MessageKind.ASSISTANT,
            content_kind=MessageContentKind.WIDGET,
            content=widget_content,
            parent_message_id=latest_user_message.id if latest_user_message else None,
            request_id=latest_user_message.request_id if latest_user_message else None,
            meta={
                "role": MessageKind.ASSISTANT.value.lower(),
                "tool_name": "compound_render_widget",
                "message": {
                    "content": [
                        {
                            "kind": MessageContentKind.WIDGET.value,
                            "value": {
                                "components": serialized_components,
                                "root": validated_payload.root,
                            },
                        }
                    ]
                },
            },
            created_at=arrow.utcnow().datetime,
        )
    )

    logger.info(
        "compound_render_widget delivered widget message: %s",
        {
            **log_context,
            "widget_message_id": str(widget_message.id),
            "sender_participant_id": str(agent_participant.id),
            "parent_message_id": str(latest_user_message.id)
            if latest_user_message
            else None,
        },
    )

    ctx.messages = [*(ctx.messages or []), widget_message]

    component_summary = ", ".join(
        f"{n.id}({n.component})" for n in validated_payload.components
    )
    return (
        f"Compound widget delivered to the user via `compound_render_widget`. "
        f"Root: {validated_payload.root}. "
        f"Components: {component_summary}."
    )


compound_render_widget.__eylo_schema_model__ = CompoundRenderWidgetInput
