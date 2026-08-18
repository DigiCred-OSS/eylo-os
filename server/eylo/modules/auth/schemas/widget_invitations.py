"""Public contracts for one-time guest-chat invitation exchange."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from eylo.common.schemas import EyloBaseApiSchema, EyloBaseRequestSchema


class WidgetInvitationIssueRequest(EyloBaseRequestSchema):
    """Identify one visitor and pin one published conversational agent."""

    agent_id: UUID
    external_id: str | None = Field(default=None, min_length=1, max_length=512)
    primary_email: EmailStr | None = None
    primary_phone: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=512)
    opener: str = Field(min_length=1, max_length=4096)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_identity_and_expiry_shape(self) -> Self:
        if not any((self.external_id, self.primary_email, self.primary_phone)):
            raise ValueError("At least one visitor identifier is required.")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must include a timezone offset.")
        return self


class WidgetInvitationIssueResponse(EyloBaseApiSchema):
    invitation_id: UUID
    contact_id: UUID
    agent_id: UUID
    agent_revision: int = Field(gt=0)
    expires_at: datetime
    invitation_url: str
    warning_codes: list[str] = Field(default_factory=list)


class WidgetInvitationExchangeRequest(EyloBaseRequestSchema):
    token: str = Field(min_length=32, max_length=512)
    request_id: UUID


class WidgetInvitationExchangeResponse(EyloBaseApiSchema):
    organization_id: UUID
    contact_id: UUID
    conversation_id: UUID
    session_token: str
    session_expires_at: datetime


__all__ = [
    "WidgetInvitationExchangeRequest",
    "WidgetInvitationExchangeResponse",
    "WidgetInvitationIssueRequest",
    "WidgetInvitationIssueResponse",
]
