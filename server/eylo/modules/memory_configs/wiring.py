"""Build memory config services from organization-scoped persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.memory_configs.resolver import MemoryConfigResolver
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService


def _provider_config_service(db: AsyncSession | None = None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(ProviderConfigRepository(session, get_secret_cipher()))


def build_memory_config_resolver(
    db: AsyncSession | None = None,
) -> MemoryConfigResolver:
    return MemoryConfigResolver(build_memory_config_service(db))


def build_memory_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
):
    from eylo.modules.memory_configs.service import MemoryConfigService

    return MemoryConfigService(
        _provider_config_service(db),
        references=references,
    )
