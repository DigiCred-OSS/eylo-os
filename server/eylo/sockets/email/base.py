"""Interface implemented by concrete email provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, ValidationError

from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundTransportKind,
)
from eylo.sockets.email.schemas import EmailMessage, EmailResponse, EmailWebhookEvent

EmailDeliverySender = Callable[
    [OutboundSendAuthorization],
    Awaitable[OutboundSendOutcome],
]


@dataclass(frozen=True, slots=True)
class EmailDeliveryCapabilities:
    """Provider guarantees relevant to safe retry and reconciliation."""

    idempotent_send: bool
    reconciliation: bool


@dataclass(frozen=True, slots=True)
class PlannedEmailDelivery:
    """One fully validated provider operation, ready for the durable boundary."""

    attempt_id: UUID
    provider_operation: str
    transport_kind: OutboundTransportKind
    destination_origin: str
    capabilities: EmailDeliveryCapabilities
    sender: EmailDeliverySender = field(repr=False, compare=False)

    async def send(
        self,
        authorization: OutboundSendAuthorization,
    ) -> OutboundSendOutcome:
        if authorization.attempt_id != self.attempt_id:
            raise ValueError("Email delivery authorization belongs to another attempt.")
        return await self.sender(authorization)


class EmailVendorAdapter(ABC):
    @abstractmethod
    def plan_delivery(
        self,
        message: EmailMessage,
        *,
        attempt_id: UUID,
    ) -> PlannedEmailDelivery:
        """Validate and construct one bounded delivery before any network send."""

    @abstractmethod
    async def verify_credentials(self) -> None:
        """Authenticate without sending a message or mutating provider state."""

    @abstractmethod
    def transform_to_platform_response(
        self,
        vendor_response: Any,
        original_message: EmailMessage,
    ) -> EmailResponse: ...

    @abstractmethod
    async def process_webhook(self, payload: dict[str, Any]) -> EmailWebhookEvent: ...

    async def verify_email(self, email: str) -> str | None:
        class EmailValidator(BaseModel):
            email: EmailStr

        try:
            return str(EmailValidator(email=email).email).lower()
        except ValidationError:
            return None

    async def close(self) -> None:
        """Release adapter resources; stateless adapters have none."""


__all__ = [
    "EmailDeliveryCapabilities",
    "EmailDeliverySender",
    "EmailVendorAdapter",
    "PlannedEmailDelivery",
]
