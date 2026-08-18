"""Durable execution path for the platform place_call agent tool."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from eylo.common.outbound import OutboundAttemptConflict, OutboundAttemptState
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.outbound.durable_execution import DurableStepContext

from .call_control import VoiceService

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext

PLACE_CALL_TOOL_NAME = "place_call"
_E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


class _PlaceCallInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_number: str
    initial_message: str = Field(min_length=1, max_length=10_000)

    @field_validator("to_number")
    @classmethod
    def validate_to_number(cls, value: str) -> str:
        value = value.strip()
        if not _E164_PATTERN.fullmatch(value):
            raise ValueError("to_number must be E.164.")
        return value


@dataclass(frozen=True, slots=True)
class PlaceCallToolExecutionOutcome:
    content: dict[str, Any]
    is_error: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


async def execute_agent_place_call_tool(
    *,
    tool_input: Mapping[str, Any],
    conversation_context: ConversationContext,
    tool_use_message_id: UUID,
    durable_context: DurableStepContext,
) -> PlaceCallToolExecutionOutcome:
    """Place one call under the committed TOOL_USE message identity."""
    try:
        requested = _PlaceCallInput.model_validate(dict(tool_input))
    except ValidationError:
        return _error("telephony_input_invalid")

    primary_agent = conversation_context.get_primary_agent()
    if (
        primary_agent is None
        or primary_agent.agent_id is None
        or primary_agent.agent_revision is None
    ):
        return _error("telephony_agent_authority_unavailable")

    try:
        result = await VoiceService().initiate_outbound_call(
            call_id=tool_use_message_id,
            to_number=requested.to_number,
            agent_id=primary_agent.agent_id,
            agent_revision=primary_agent.agent_revision,
            organization_id=conversation_context.conversation.organization_id,
            initial_message=requested.initial_message,
            context={
                "conversation_id": str(conversation_context.conversation.id),
                "tool_use_message_id": str(tool_use_message_id),
            },
            durable_context=durable_context,
        )
    except NotConfiguredError:
        return _error("telephony_config_unavailable")
    except OutboundAttemptConflict:
        return _error("telephony_delivery_conflict")

    metadata = {
        "telephony_delivery": True,
        "telephony_delivery_status": result["status"],
        "call_id": result["call_id"],
        "provider_call_id": result.get("call_sid"),
        "outbound_attempt_id": result["outbound_attempt_id"],
        "provider_config_id": result["provider_config_id"],
        "provider_config_revision": result["provider_config_revision"],
    }
    if result["status"] == OutboundAttemptState.SUCCEEDED.value:
        return PlaceCallToolExecutionOutcome(
            content={
                "status": "accepted",
                "call_id": result["call_id"],
            },
            is_error=False,
            metadata=metadata,
        )
    code = (
        "telephony_delivery_unknown"
        if result["status"] == OutboundAttemptState.UNKNOWN.value
        else "telephony_delivery_rejected"
    )
    return _error(code, metadata=metadata)


def _error(
    code: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> PlaceCallToolExecutionOutcome:
    return PlaceCallToolExecutionOutcome(
        content={"kind": "telephony_error", "error": code},
        is_error=True,
        metadata={} if metadata is None else metadata,
    )


__all__ = [
    "PLACE_CALL_TOOL_NAME",
    "PlaceCallToolExecutionOutcome",
    "execute_agent_place_call_tool",
]
