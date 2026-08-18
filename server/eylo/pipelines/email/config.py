"""Compose validated platform email values into socket adapter configs."""

from __future__ import annotations

from pydantic import ValidationError

from eylo.modules.email_configs.catalog import EmailProviders
from eylo.modules.email_configs.domain import EmailProviderConfig, InvalidEmailConfig
from eylo.sockets.email.schemas import EmailConfig, SMTPConfig, SendGridConfig


def build_email_runtime_config(config: EmailProviderConfig) -> EmailConfig:
    values = dict(config.config)
    try:
        if config.provider is EmailProviders.SENDGRID:
            return SendGridConfig(
                **values,
                api_key=config.secret("api_key"),
            )
        if config.provider is EmailProviders.SMTP:
            return SMTPConfig(
                **values,
                smtp_password=config.secret("smtp_password"),
            )
    except ValidationError:
        raise InvalidEmailConfig(
            f"Invalid runtime config for {config.provider.value}."
        ) from None
    raise InvalidEmailConfig(f"Unsupported email provider: {config.provider}")
