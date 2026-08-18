"""Asynchronous SendGrid Web API adapter."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import httpx

from eylo.common.http_egress import (
    HttpDestinationPolicy,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpEgressResponse,
    HttpOrigin,
    HttpRoutePolicy,
    OriginBoundHeaders,
)
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
from eylo.sockets.email.exceptions import EmailVendorError
from eylo.sockets.email.schemas import (
    EmailMessage,
    EmailPriority,
    EmailResponse,
    EmailStatus,
    EmailWebhookEvent,
    SendGridConfig,
)
from eylo.sockets.http import SafeHttpTransport

logger = logging.getLogger(__name__)

_API_BASE = "https://api.sendgrid.com/v3"
_MAIL_SEND_URL = f"{_API_BASE}/mail/send"
_SENDGRID_ORIGIN = HttpOrigin.parse("https://api.sendgrid.com")
_DELIVERY_CAPABILITIES = EmailDeliveryCapabilities(
    idempotent_send=False,
    reconciliation=False,
)
_DNS_FAILURES = frozenset({"dns_resolution_empty", "dns_resolution_failed"})


class SendGridHttpTransport(Protocol):
    async def send(self, request: HttpEgressRequest) -> HttpEgressResponse: ...


class SendGridAdapter(EmailVendorAdapter):
    def __init__(
        self,
        config: SendGridConfig,
        *,
        transport: SendGridHttpTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport or SafeHttpTransport()

    def plan_delivery(
        self,
        message: EmailMessage,
        *,
        attempt_id: UUID,
    ) -> PlannedEmailDelivery:
        body = json.dumps(
            _sendgrid_payload(message, attempt_id=attempt_id),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        request = HttpEgressRequest(
            method="POST",
            url=_MAIL_SEND_URL,
            policy=HttpDestinationPolicy(
                primary=HttpRoutePolicy(
                    origin=_SENDGRID_ORIGIN,
                    path_prefix="/v3/mail/send",
                ),
                max_redirects=0,
            ),
            headers={"Content-Type": "application/json"},
            origin_headers=OriginBoundHeaders(
                origin=_SENDGRID_ORIGIN,
                values={
                    "Authorization": (
                        f"Bearer {self.config.api_key.get_secret_value()}"
                    )
                },
            ),
            body=body,
            response_body_limit=65_536,
            total_timeout_seconds=self.config.timeout,
        )
        return PlannedEmailDelivery(
            attempt_id=attempt_id,
            provider_operation="email.send.sendgrid",
            transport_kind=OutboundTransportKind.HTTP,
            destination_origin=str(_SENDGRID_ORIGIN),
            capabilities=_DELIVERY_CAPABILITIES,
            sender=lambda authorization: self._send_delivery(
                request,
                authorization=authorization,
            ),
        )

    async def _send_delivery(
        self,
        request: HttpEgressRequest,
        *,
        authorization: OutboundSendAuthorization,
    ) -> OutboundSendOutcome:
        del authorization
        try:
            response = await self._transport.send(request)
        except HttpEgressPolicyError as error:
            if error.code in _DNS_FAILURES:
                return OutboundSendRetryable("sendgrid_dns_unavailable")
            if error.code == "transport_failed":
                return OutboundSendUnknown("sendgrid_transport_unconfirmed")
            if error.code in {
                "response_body_too_large",
                "response_headers_too_large",
            }:
                return OutboundSendUnknown("sendgrid_response_unconfirmed")
            return OutboundSendTerminal("sendgrid_egress_rejected")
        except TimeoutError:
            return OutboundSendUnknown("sendgrid_timeout_unconfirmed")

        if response.status_code == 202:
            return OutboundSendSucceeded(
                provider_reference=_message_id(response),
                status_code=response.status_code,
            )
        if response.status_code == 429:
            return OutboundSendRetryable(
                "sendgrid_rate_limited",
                status_code=response.status_code,
            )
        if response.status_code == 408 or response.status_code >= 500:
            return OutboundSendUnknown(
                "sendgrid_response_unconfirmed",
                status_code=response.status_code,
            )
        return OutboundSendTerminal(
            "sendgrid_request_rejected",
            status_code=response.status_code,
        )

    async def verify_credentials(self) -> None:
        try:
            async with self._client() as client:
                response = await client.get(f"{_API_BASE}/scopes")
                response.raise_for_status()
                payload = response.json()
            scopes = payload.get("scopes") if isinstance(payload, dict) else None
            if not isinstance(scopes, list) or "mail.send" not in scopes:
                raise EmailVendorError("SendGrid key does not grant mail.send.")
        except Exception as error:
            _log_failure("verify", error)
            raise EmailVendorError("SendGrid credential verification failed.") from None

    def transform_to_platform_response(
        self,
        vendor_response: Any,
        original_message: EmailMessage,
    ) -> EmailResponse:
        status_code = getattr(vendor_response, "status_code", None)
        headers = getattr(vendor_response, "headers", {})
        return EmailResponse(
            message_id=headers.get("X-Message-Id", ""),
            status=(EmailStatus.SENT if status_code == 202 else EmailStatus.FAILED),
            vendor="sendgrid",
            to=original_message.to,
            subject=original_message.subject,
            metadata={"status_code": status_code},
        )

    async def process_webhook(self, payload: dict[str, Any]) -> EmailWebhookEvent:
        try:
            event_type = _event_status(str(payload.get("event", "")))
            return EmailWebhookEvent(
                event_type=event_type,
                message_id=str(payload.get("sg_message_id", "")),
                email=payload.get("email", ""),
                timestamp=datetime.fromtimestamp(
                    float(payload.get("timestamp", 0)),
                    tz=timezone.utc,
                ),
                vendor="sendgrid",
                reason=payload.get("reason"),
                metadata=payload,
            )
        except Exception:
            raise EmailVendorError("SendGrid webhook payload is invalid.") from None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            trust_env=False,
            headers={
                "Authorization": (f"Bearer {self.config.api_key.get_secret_value()}"),
                "Content-Type": "application/json",
            },
        )


def _sendgrid_payload(
    message: EmailMessage,
    *,
    attempt_id: UUID,
) -> dict[str, object]:
    personalization: dict[str, object] = {
        "to": [{"email": str(address)} for address in message.to],
        "custom_args": {"eylo_attempt_id": attempt_id.hex},
    }
    if message.cc:
        personalization["cc"] = [{"email": str(address)} for address in message.cc]
    if message.bcc:
        personalization["bcc"] = [{"email": str(address)} for address in message.bcc]
    headers = dict(message.headers or {})
    priority_header = _priority_header(message.priority)
    if priority_header is not None:
        headers["X-Priority"] = priority_header
    if headers:
        personalization["headers"] = headers

    content = []
    if message.text_content:
        content.append({"type": "text/plain", "value": message.text_content})
    if message.html_content:
        content.append({"type": "text/html", "value": message.html_content})

    payload: dict[str, object] = {
        "personalizations": [personalization],
        "from": {
            "email": str(message.from_email),
            "name": message.from_name,
        },
        "subject": message.subject,
        "content": content,
    }
    if message.reply_to:
        payload["reply_to"] = {"email": str(message.reply_to)}
    if message.attachments:
        payload["attachments"] = [
            {
                "content": attachment.content,
                "filename": attachment.filename,
                "type": attachment.content_type,
                "disposition": "attachment",
            }
            for attachment in message.attachments
        ]
    return payload


def _priority_header(priority: EmailPriority) -> str | None:
    return {
        EmailPriority.HIGH: "1",
        EmailPriority.NORMAL: None,
        EmailPriority.LOW: "5",
    }[priority]


def _event_status(event: str) -> EmailStatus:
    return {
        "delivered": EmailStatus.DELIVERED,
        "bounce": EmailStatus.BOUNCED,
        "dropped": EmailStatus.REJECTED,
        "deferred": EmailStatus.PENDING,
        "processed": EmailStatus.SENT,
        "open": EmailStatus.OPENED,
        "click": EmailStatus.CLICKED,
    }.get(event, EmailStatus.PENDING)


def _message_id(response: HttpEgressResponse) -> str | None:
    values = response.header_values("x-message-id")
    if len(values) != 1:
        return None
    value = values[0].strip()
    return value if 0 < len(value) <= 320 else None


def _log_failure(operation: str, error: Exception) -> None:
    status_code = (
        error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    )
    logger.warning(
        "SendGrid request failed operation=%s category=%s status=%s",
        operation,
        type(error).__name__,
        status_code,
    )
