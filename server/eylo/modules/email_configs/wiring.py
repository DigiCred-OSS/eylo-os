"""Dependency wiring for email config services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.email_configs.resolver import EmailConfigResolver
from eylo.modules.email_configs.service import EmailConfigService
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService


def _build_provider_config_service(db: AsyncSession | None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )


def build_email_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
) -> EmailConfigService:
    return EmailConfigService(
        _build_provider_config_service(db),
        references=references,
    )


def build_email_config_resolver(db: AsyncSession | None = None) -> EmailConfigResolver:
    return EmailConfigResolver(build_email_config_service(db))
