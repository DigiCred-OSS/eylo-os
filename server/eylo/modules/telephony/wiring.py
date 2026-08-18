"""Dependency wiring for telephony provider configuration."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.telephony.provider_config_service import (
    TelephonyConfigResolver,
    TelephonyConfigService,
)


def _build_provider_config_service(db: AsyncSession | None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )


def build_telephony_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
) -> TelephonyConfigService:
    return TelephonyConfigService(
        _build_provider_config_service(db),
        references=references,
    )


def build_telephony_config_resolver(
    db: AsyncSession | None = None,
) -> TelephonyConfigResolver:
    return TelephonyConfigResolver(build_telephony_config_service(db))
