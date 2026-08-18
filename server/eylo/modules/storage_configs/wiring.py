"""Dependency wiring for storage config services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.storage_configs.resolver import StorageConfigResolver
from eylo.modules.storage_configs.service import (
    StorageConfigReferences,
    StorageConfigService,
)


def _build_provider_config_service(db: AsyncSession | None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )


def build_storage_config_service(
    db: AsyncSession | None = None,
    *,
    references: StorageConfigReferences | None = None,
) -> StorageConfigService:
    return StorageConfigService(
        _build_provider_config_service(db),
        references,
    )


def build_storage_config_resolver(db: AsyncSession | None = None) -> StorageConfigResolver:
    return StorageConfigResolver(build_storage_config_service(db))
