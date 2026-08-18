"""Construct one email adapter from one explicit typed runtime config."""

from __future__ import annotations

from eylo.sockets.email.base import EmailVendorAdapter
from eylo.sockets.email.schemas import EmailConfig, SMTPConfig, SendGridConfig
from eylo.sockets.email.sendgrid import SendGridAdapter, SendGridHttpTransport
from eylo.sockets.email.smtp import SMTPAdapter


class EmailFactory:
    def __init__(
        self,
        config: EmailConfig,
        *,
        sendgrid_transport: SendGridHttpTransport | None = None,
    ) -> None:
        self.config = config
        self._adapter = _build_adapter(
            config,
            sendgrid_transport=sendgrid_transport,
        )

    def get_adapter(self) -> EmailVendorAdapter:
        return self._adapter

    async def close(self) -> None:
        await self._adapter.close()

    @property
    def vendor(self) -> str:
        return self.config.vendor


def _build_adapter(
    config: EmailConfig,
    *,
    sendgrid_transport: SendGridHttpTransport | None,
) -> EmailVendorAdapter:
    if isinstance(config, SendGridConfig):
        return SendGridAdapter(config, transport=sendgrid_transport)
    if isinstance(config, SMTPConfig):
        return SMTPAdapter(config)
    raise TypeError(f"Unsupported email config type: {type(config).__name__}")
