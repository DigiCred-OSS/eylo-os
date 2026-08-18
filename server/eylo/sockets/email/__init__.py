"""Email Socket Module.

This module provides email sending through SendGrid and SMTP adapters.

Email sockets are stateless. Application code uses ``pipelines/email`` so one
stable owner and exact provider-config revision exist before an adapter plans
or sends a message.
"""

from eylo.sockets.email.base import (
    EmailDeliveryCapabilities,
    EmailVendorAdapter,
    PlannedEmailDelivery,
)
from eylo.sockets.email.exceptions import (
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailError,
    EmailRateLimitError,
    EmailSendError,
    EmailValidationError,
    EmailVendorError,
)
from eylo.sockets.email.factory import EmailFactory
from eylo.sockets.email.schemas import (
    EmailAttachment,
    EmailConfig,
    EmailMessage,
    EmailPriority,
    EmailResponse,
    EmailStatus,
    EmailWebhookEvent,
    SMTPConfig,
    SendGridConfig,
)

__all__ = [
    # Core interfaces
    "EmailVendorAdapter",
    "EmailDeliveryCapabilities",
    "PlannedEmailDelivery",
    "EmailFactory",
    # Schemas
    "EmailConfig",
    "SendGridConfig",
    "SMTPConfig",
    "EmailAttachment",
    "EmailMessage",
    "EmailResponse",
    "EmailStatus",
    "EmailPriority",
    "EmailWebhookEvent",
    # Exceptions
    "EmailError",
    "EmailSendError",
    "EmailValidationError",
    "EmailVendorError",
    "EmailConfigurationError",
    "EmailRateLimitError",
    "EmailAuthenticationError",
]
