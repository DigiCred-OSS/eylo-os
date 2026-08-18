"""Certificate-validating authenticated SMTP adapter."""

from __future__ import annotations

import asyncio
import base64
import logging
import socket
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.message import EmailMessage as MIMEMessage
from email.utils import formataddr
from ipaddress import ip_address
from typing import Any
from uuid import UUID

import aiosmtplib
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPConnectResponseError,
    SMTPNotSupported,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPTimeoutError,
)

from eylo.common.http_egress import MAX_REQUEST_BODY_BYTES
from eylo.common.outbound import (
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendRetryable,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.sockets.email.base import (
    EmailDeliveryCapabilities,
    EmailVendorAdapter,
    PlannedEmailDelivery,
)
from eylo.sockets.email.exceptions import (
    EmailConfigurationError,
    EmailVendorError,
)
from eylo.sockets.email.schemas import (
    EmailMessage,
    EmailPriority,
    EmailResponse,
    EmailStatus,
    EmailWebhookEvent,
    SMTPConfig,
)

logger = logging.getLogger(__name__)
_DELIVERY_CAPABILITIES = EmailDeliveryCapabilities(
    idempotent_send=False,
    reconciliation=False,
)


class _SMTPPrewireError(Exception):
    """Safe category for a failure known to precede MAIL/RCPT/DATA."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class SMTPAdapter(EmailVendorAdapter):
    def __init__(self, config: SMTPConfig) -> None:
        self.config = config

    def plan_delivery(
        self,
        message: EmailMessage,
        *,
        attempt_id: UUID,
    ) -> PlannedEmailDelivery:
        mime_message = _to_mime_message(message, attempt_id=attempt_id)
        if len(mime_message.as_bytes()) > MAX_REQUEST_BODY_BYTES:
            raise EmailConfigurationError(
                "Serialized email exceeds the outbound delivery limit."
            )
        recipients = [
            str(address)
            for address in [*message.to, *(message.cc or []), *(message.bcc or [])]
        ]
        return PlannedEmailDelivery(
            attempt_id=attempt_id,
            provider_operation="email.send.smtp",
            transport_kind=OutboundTransportKind.PROVIDER_SDK,
            destination_origin=(
                f"smtp+{self.config.smtp_security}://"
                f"{self.config.smtp_host}:{self.config.smtp_port}"
            ),
            capabilities=_DELIVERY_CAPABILITIES,
            sender=lambda authorization: self._send_delivery(
                mime_message,
                recipients,
                envelope_sender=str(message.from_email),
                authorization=authorization,
            ),
        )

    async def _send_delivery(
        self,
        mime_message: MIMEMessage,
        recipients: list[str],
        *,
        envelope_sender: str,
        authorization: OutboundSendAuthorization,
    ) -> OutboundSendOutcome:
        del authorization
        outcome: OutboundSendOutcome | None = None
        delivery_started = False
        try:
            async with asyncio.timeout(self.config.timeout):
                async with _authenticated_client(self.config) as client:
                    delivery_started = True
                    outcome = await _send_connected(
                        client,
                        mime_message,
                        recipients,
                        envelope_sender=envelope_sender,
                    )
        except Exception as error:
            if outcome is not None:
                return outcome
            _log_failure("send", error)
            if delivery_started:
                return OutboundSendUnknown("smtp_delivery_unconfirmed")
            return _prewire_outcome(error)
        assert outcome is not None
        return outcome

    async def verify_credentials(self) -> None:
        try:
            async with asyncio.timeout(self.config.timeout):
                async with _authenticated_client(self.config):
                    pass
        except Exception as error:
            _log_failure("verify", error)
            raise EmailVendorError("SMTP credential verification failed.") from None

    def transform_to_platform_response(
        self,
        vendor_response: Any,
        original_message: EmailMessage,
    ) -> EmailResponse:
        return EmailResponse(
            message_id=str(vendor_response),
            status=EmailStatus.SENT,
            vendor="smtp",
            to=original_message.to,
            subject=original_message.subject,
        )

    async def process_webhook(self, payload: dict[str, Any]) -> EmailWebhookEvent:
        raise EmailVendorError("SMTP adapter does not support webhooks.")


def _to_mime_message(
    message: EmailMessage,
    *,
    attempt_id: UUID,
) -> MIMEMessage:
    mime_message = MIMEMessage()
    mime_message["Message-ID"] = _message_id(attempt_id)
    mime_message["Subject"] = message.subject
    mime_message["From"] = formataddr((message.from_name, str(message.from_email)))
    mime_message["To"] = ", ".join(str(address) for address in message.to)
    if message.cc:
        mime_message["Cc"] = ", ".join(str(address) for address in message.cc)
    if message.reply_to:
        mime_message["Reply-To"] = str(message.reply_to)
    for name, value in (message.headers or {}).items():
        mime_message[name] = value
    priority_header = _priority_header(message.priority)
    if priority_header is not None:
        mime_message["X-Priority"] = priority_header

    if message.text_content:
        mime_message.set_content(message.text_content)
        if message.html_content:
            mime_message.add_alternative(message.html_content, subtype="html")
    else:
        assert message.html_content is not None
        mime_message.set_content(message.html_content, subtype="html")

    for attachment in message.attachments or []:
        try:
            content = base64.b64decode(attachment.content, validate=True)
        except ValueError:
            raise EmailConfigurationError(
                f"Attachment {attachment.filename} is not valid base64."
            ) from None
        main_type, sub_type = attachment.content_type.split("/", maxsplit=1)
        mime_message.add_attachment(
            content,
            maintype=main_type,
            subtype=sub_type,
            filename=attachment.filename,
        )
    return mime_message


async def _send_connected(
    client: aiosmtplib.SMTP,
    mime_message: MIMEMessage,
    recipients: list[str],
    *,
    envelope_sender: str,
) -> OutboundSendOutcome:
    try:
        await client.send_message(
            mime_message,
            sender=envelope_sender,
            recipients=recipients,
        )
    except SMTPRecipientsRefused as error:
        codes = [recipient.code for recipient in error.recipients]
        if codes and all(400 <= code <= 499 for code in codes):
            return OutboundSendRetryable("smtp_temporary_rejection")
        return OutboundSendTerminal("smtp_permanent_rejection")
    except SMTPResponseException as error:
        return _smtp_response_outcome(error.code)
    except SMTPNotSupported:
        return OutboundSendTerminal("smtp_operation_unsupported")
    except Exception:
        return OutboundSendUnknown("smtp_delivery_unconfirmed")
    return OutboundSendSucceeded(provider_reference=str(mime_message["Message-ID"]))


def _prewire_outcome(error: Exception) -> OutboundSendOutcome:
    if isinstance(error, _SMTPPrewireError):
        outcome = OutboundSendRetryable if error.retryable else OutboundSendTerminal
        return outcome(error.code)
    if isinstance(error, SMTPAuthenticationError):
        return OutboundSendTerminal("smtp_authentication_rejected")
    if isinstance(error, SMTPConnectResponseError):
        return _smtp_response_outcome(error.code)
    if isinstance(error, (SMTPNotSupported, ssl.SSLError, ValueError)):
        return OutboundSendTerminal("smtp_configuration_rejected")
    if isinstance(
        error,
        (SMTPConnectError, SMTPTimeoutError, TimeoutError, ConnectionError, OSError),
    ):
        return OutboundSendRetryable("smtp_connection_unavailable")
    return OutboundSendRetryable("smtp_preflight_failed")


def _smtp_response_outcome(code: int) -> OutboundSendOutcome:
    if 400 <= code <= 499:
        return OutboundSendRetryable(
            "smtp_temporary_rejection",
            status_code=code,
        )
    return OutboundSendTerminal(
        "smtp_permanent_rejection",
        status_code=code if 100 <= code <= 599 else None,
    )


def _message_id(attempt_id: UUID) -> str:
    return f"<eylo.{attempt_id.hex}@id.eylo.ai>"


@asynccontextmanager
async def _authenticated_client(config: SMTPConfig) -> AsyncIterator[aiosmtplib.SMTP]:
    connected_socket = await _connect_public_socket(
        config.smtp_host,
        config.smtp_port,
    )
    implicit_tls = config.smtp_security == "implicit_tls"
    client = aiosmtplib.SMTP(
        hostname=config.smtp_host,
        sock=connected_socket,
        timeout=config.timeout,
        use_tls=implicit_tls,
        start_tls=not implicit_tls,
        validate_certs=True,
    )
    try:
        async with client:
            await client.login(
                config.smtp_username,
                config.smtp_password.get_secret_value(),
            )
            yield client
    finally:
        connected_socket.close()


async def _connect_public_socket(host: str, port: int) -> socket.socket:
    loop = asyncio.get_running_loop()
    try:
        addresses = await loop.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        raise _SMTPPrewireError(
            "smtp_dns_unavailable",
            retryable=True,
        ) from None
    resolved = {ip_address(address[4][0]) for address in addresses}
    if not resolved or any(not address.is_global for address in resolved):
        raise _SMTPPrewireError(
            "smtp_destination_rejected",
            retryable=False,
        )

    for family, socket_type, protocol, _, socket_address in addresses:
        connected_socket = socket.socket(family, socket_type, protocol)
        connected_socket.setblocking(False)
        try:
            await loop.sock_connect(connected_socket, socket_address)
        except OSError:
            connected_socket.close()
            continue
        return connected_socket
    raise _SMTPPrewireError(
        "smtp_connection_unavailable",
        retryable=True,
    )


def _priority_header(priority: EmailPriority) -> str | None:
    return {
        EmailPriority.HIGH: "1",
        EmailPriority.NORMAL: None,
        EmailPriority.LOW: "5",
    }[priority]


def _log_failure(operation: str, error: Exception) -> None:
    logger.warning(
        "SMTP request failed operation=%s category=%s",
        operation,
        type(error).__name__,
    )
