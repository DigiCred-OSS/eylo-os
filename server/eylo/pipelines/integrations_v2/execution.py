"""Execute one curated vendor tool from committed product intent.

Policy is resolved live through the module service. The handler is curated
Python that may make several vendor calls rather than one declarative request.

Nothing here decides policy. `resolve_for_execution` already refused a disabled
or approval-gated tool before a client was ever constructed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import ValidationError

from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.base import AuthRequiredEvent
from eylo.modules.integrations_v2.domain.errors import (
    IntegrationsV2Error,
    ToolApprovalRequiredError,
    ToolExecutionBlockedError,
)
from eylo.modules.integrations_v2.services.installations import (
    CuratedIntegrationService,
)
from eylo.pipelines.outbound.durable_execution import DurableStepContext

from .contracts import VendorToolContext, VendorToolError
from .http_client import DurableMutationOwner, GuardedVendorClient, VendorTransport
from .registry import CuratedRegistry, load_vendors
from .resolution import resolve_vendor_auth

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext


@dataclass(frozen=True, slots=True)
class CuratedToolExecutionOutcome:
    """Safe content and metadata consumed by the conversation adapter."""

    content: dict[str, Any] = field(repr=False)
    is_error: bool
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", dict(self.content))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


async def execute_curated_tool(
    *,
    tool_id: UUID,
    tool_input: Mapping[str, Any],
    conversation_context: ConversationContext,
    tool_use_message_id: UUID,
    durable_context: DurableStepContext,
    registry: CuratedRegistry | None = None,
    transport: VendorTransport | None = None,
    service: CuratedIntegrationService | None = None,
) -> CuratedToolExecutionOutcome:
    """Authorize, resolve, and run one curated tool call."""
    organization_id = UUID(str(conversation_context.conversation.organization_id))
    registry = registry or load_vendors()

    try:
        grant = await (service or CuratedIntegrationService()).resolve_for_execution(
            organization_id=organization_id,
            tool_id=tool_id,
        )
    except (ToolExecutionBlockedError, ToolApprovalRequiredError) as error:
        return _error_outcome(error.code, approval_required=True)
    except IntegrationsV2Error as error:
        return _error_outcome(error.code)

    spec = registry.tool(grant.wire_id)
    if spec is None:
        return _error_outcome("tool_binding_unavailable")

    try:
        payload = spec.input_model.model_validate(dict(tool_input))
    except ValidationError:
        return _error_outcome("tool_input_invalid")

    try:
        contact_id = _primary_contact_id(conversation_context)
        resolved = await resolve_vendor_auth(
            grant=grant,
            contact_id=contact_id,
            registry=registry,
        )
    except IntegrationsV2Error as error:
        auth_required = error.code == "auth_required"
        if auth_required and contact_id is not None:
            emit_ephemeral(
                AuthRequiredEvent(
                    conversation_id=UUID(str(conversation_context.conversation.id)),
                    organization_id=organization_id,
                    integration_id=grant.installation_id,
                    vendor=grant.vendor,
                    auth_kind=grant.auth_kind.value,
                    integration_name=resolved_vendor_name(registry, grant.vendor),
                    reason="authorization_required",
                    contact_id=contact_id,
                    message=(
                        f"Connect {resolved_vendor_name(registry, grant.vendor)} "
                        "so the Agent can continue."
                    ),
                )
            )
        return _error_outcome(
            error.code,
            auth_required=auth_required,
            vendor=grant.vendor,
        )

    client = GuardedVendorClient(
        base_url=resolved.base_url,
        auth=resolved.auth,
        vendor=resolved.vendor.vendor,
        transport=transport,
        static_headers=dict(resolved.vendor.static_headers),
        owner=DurableMutationOwner(
            organization_id=organization_id,
            tool_use_message_id=tool_use_message_id,
            tool_id=tool_id,
            durable_context=durable_context,
        ),
    )
    context = VendorToolContext(
        http=client,
        account=resolved.account,
        effect=spec.effect,
    )

    try:
        result = await spec.handler(payload, context)
    except VendorToolError as error:
        return _error_outcome(error.code, vendor=grant.vendor)

    return CuratedToolExecutionOutcome(
        content={"kind": "curated_result", "data": result},
        is_error=False,
        metadata={
            "curated_execution": True,
            "vendor": grant.vendor,
            "wire_id": grant.wire_id,
            "effect": spec.effect.value,
        },
    )


def _primary_contact_id(conversation_context: ConversationContext) -> UUID | None:
    participant = conversation_context.get_primary_contact()
    if participant is None:
        return None
    try:
        return UUID(str(participant.entity_id))
    except (TypeError, ValueError):
        return None


def resolved_vendor_name(registry: CuratedRegistry, vendor: str) -> str:
    spec = registry.vendor(vendor)
    return spec.display_name if spec is not None else vendor


def _error_outcome(
    code: str,
    *,
    auth_required: bool = False,
    approval_required: bool = False,
    vendor: str | None = None,
) -> CuratedToolExecutionOutcome:
    kind = "auth_required" if auth_required else "curated_error"
    metadata: dict[str, Any] = {
        "curated_execution": True,
        "auth_required": auth_required,
        "approval_required": approval_required,
        "error_code": code,
    }
    if vendor is not None:
        metadata["vendor"] = vendor
    return CuratedToolExecutionOutcome(
        content={"kind": kind, "error": code},
        is_error=True,
        metadata=metadata,
    )


__all__ = [
    "CuratedToolExecutionOutcome",
    "execute_curated_tool",
]
