"""Provider-neutral email messages plus strict provider runtime configs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

_CONTENT_TYPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
_HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
_RESERVED_HEADERS = frozenset(
    {
        "bcc",
        "cc",
        "content-type",
        "from",
        "message-id",
        "mime-version",
        "reply-to",
        "subject",
        "to",
    }
)


class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    OPENED = "opened"
    CLICKED = "clicked"


class EmailPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EmailAttachment(BaseModel):
    """One base64-encoded attachment preserved by every provider adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=255)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not _CONTENT_TYPE_PATTERN.fullmatch(normalized):
            raise ValueError("content_type must be a MIME media type.")
        return normalized


class EmailMessage(BaseModel):
    """Email semantics supported without silent loss by every adapter."""

    model_config = ConfigDict(extra="forbid")

    to: list[EmailStr] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=998)
    html_content: str | None = None
    text_content: str | None = None
    from_email: EmailStr
    from_name: str = Field(min_length=1, max_length=255)
    reply_to: EmailStr | None = None
    cc: list[EmailStr] | None = None
    bcc: list[EmailStr] | None = None
    attachments: list[EmailAttachment] | None = None
    headers: dict[str, str] | None = None
    priority: EmailPriority = EmailPriority.NORMAL

    @field_validator("cc", "bcc")
    @classmethod
    def validate_optional_recipients(
        cls,
        value: list[EmailStr] | None,
    ) -> list[EmailStr] | None:
        if value == []:
            raise ValueError("Recipient lists cannot be empty.")
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(
        cls,
        value: dict[str, str] | None,
    ) -> dict[str, str] | None:
        if value is None:
            return None
        for name, header_value in value.items():
            if (
                not _HEADER_NAME_PATTERN.fullmatch(name)
                or name.lower() in _RESERVED_HEADERS
                or "\r" in header_value
                or "\n" in header_value
            ):
                raise ValueError(f"Unsafe or reserved email header: {name}")
        return value

    @model_validator(mode="after")
    def validate_content(self) -> EmailMessage:
        if not (self.text_content and self.text_content.strip()) and not (
            self.html_content and self.html_content.strip()
        ):
            raise ValueError("Email requires non-empty text or HTML content.")
        return self


class EmailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    status: EmailStatus
    vendor: Literal["sendgrid", "smtp"]
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    to: list[EmailStr]
    subject: str
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class _EmailRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    default_from_email: EmailStr
    default_from_name: str = Field(min_length=1, max_length=255)
    timeout: float = Field(gt=0, le=60)


class SendGridConfig(_EmailRuntimeConfig):
    vendor: Literal["sendgrid"] = "sendgrid"
    api_key: SecretStr


class SMTPConfig(_EmailRuntimeConfig):
    vendor: Literal["smtp"] = "smtp"
    smtp_host: str = Field(min_length=1, max_length=253)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_username: str = Field(min_length=1, max_length=320)
    smtp_password: SecretStr
    smtp_security: Literal["implicit_tls", "starttls"]


EmailConfig = Annotated[SendGridConfig | SMTPConfig, Field(discriminator="vendor")]


class EmailWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EmailStatus
    message_id: str
    email: EmailStr
    timestamp: datetime
    vendor: Literal["sendgrid", "smtp"]
    reason: str | None = None
    metadata: dict[str, Any] | None = None
