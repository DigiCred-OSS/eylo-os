"""Build sandbox config services from organization-scoped persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.sandbox_configs.resolver import SandboxConfigResolver


def _provider_config_service(db: AsyncSession | None = None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(ProviderConfigRepository(session, get_secret_cipher()))


def build_sandbox_config_resolver(
    db: AsyncSession | None = None,
) -> SandboxConfigResolver:
    return SandboxConfigResolver(build_sandbox_config_service(db))


def build_sandbox_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
):
    from eylo.modules.sandbox_configs.service import SandboxConfigService

    return SandboxConfigService(
        _provider_config_service(db),
        references=references,
    )
