"""Durable execution path for the platform send_email agent tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError

from eylo.common.outbound import (
    OutboundAttemptConflict,
    OutboundAttemptState,
    OutboundOwnerKind,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.outbound.durable_execution import DurableStepContext

from .delivery import EmailDeliveryUnsupported, send_organization_email

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.sockets.email.sendgrid import SendGridHttpTransport

SEND_EMAIL_TOOL_NAME = "send_email"


class _SendEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=998)
    text_body: str = Field(min_length=1)
    html_body: str | None = None


@dataclass(frozen=True, slots=True)
class EmailToolExecutionOutcome:
    content: dict[str, Any]
    is_error: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


async def execute_agent_email_tool(
    *,
    tool_input: Mapping[str, Any],
    conversation_context: ConversationContext,
    tool_use_message_id: UUID,
    durable_context: DurableStepContext,
    sendgrid_transport: SendGridHttpTransport | None = None,
) -> EmailToolExecutionOutcome:
    """Send once under the committed TOOL_USE message and exact agent grant."""
    try:
        requested = _SendEmailInput.model_validate(dict(tool_input))
    except ValidationError:
        return _error("email_input_invalid")

    agent = conversation_context.primary_agent
    raw_config_id = getattr(agent, "email_provider_config_id", None)
    raw_config_revision = getattr(agent, "email_provider_config_revision", None)
    try:
        provider_config_id = UUID(str(raw_config_id))
    except (TypeError, ValueError):
        return _error("email_config_unavailable")
    if (
        isinstance(raw_config_revision, bool)
        or not isinstance(raw_config_revision, int)
        or raw_config_revision <= 0
    ):
        return _error("email_config_unavailable")

    try:
        result = await send_organization_email(
            organization_id=UUID(
                str(conversation_context.conversation.organization_id)
            ),
            owner_kind=OutboundOwnerKind.TOOL_CALL,
            owner_id=tool_use_message_id,
            provider_config_id=provider_config_id,
            provider_config_revision=raw_config_revision,
            to_email=str(requested.to_email),
            subject=requested.subject,
            text_body=requested.text_body,
            html_body=requested.html_body,
            durable_context=durable_context,
            sendgrid_transport=sendgrid_transport,
        )
    except NotConfiguredError:
        return _error("email_config_unavailable")
    except EmailDeliveryUnsupported:
        return _error("email_delivery_unsupported")
    except OutboundAttemptConflict:
        return _error("email_delivery_conflict")

    metadata = {
        "email_delivery": True,
        "email_delivery_status": result.status,
        "outbound_attempt_id": str(result.attempt_id),
        "provider_config_id": str(provider_config_id),
        "provider_config_revision": raw_config_revision,
    }
    if result.state is OutboundAttemptState.SUCCEEDED:
        return EmailToolExecutionOutcome(
            content={
                "status": "accepted",
                "message_id": result.tracking_id,
            },
            is_error=False,
            metadata=metadata,
        )
    code = (
        "email_delivery_unknown"
        if result.state is OutboundAttemptState.UNKNOWN
        else "email_delivery_rejected"
    )
    return _error(code, metadata=metadata)


def _error(
    code: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> EmailToolExecutionOutcome:
    return EmailToolExecutionOutcome(
        content={"kind": "email_error", "error": code},
        is_error=True,
        metadata={} if metadata is None else metadata,
    )


__all__ = [
    "EmailToolExecutionOutcome",
    "SEND_EMAIL_TOOL_NAME",
    "execute_agent_email_tool",
]
