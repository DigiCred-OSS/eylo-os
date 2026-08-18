"""Build embedding config application services from org-scoped persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.config import settings
from eylo.common.database import get_transaction
from eylo.modules.embedding_configs.domain import EmbeddingEndpointPolicy
from eylo.modules.embedding_configs.resolver import EmbeddingConfigResolver
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService


def _provider_config_service(db: AsyncSession | None = None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(ProviderConfigRepository(session, get_secret_cipher()))


def build_embedding_config_resolver(
    db: AsyncSession | None = None,
) -> EmbeddingConfigResolver:
    return EmbeddingConfigResolver(build_embedding_config_service(db))


def build_embedding_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
):
    from eylo.modules.embedding_configs.service import EmbeddingConfigService

    return EmbeddingConfigService(
        _provider_config_service(db),
        endpoint_policy=build_embedding_endpoint_policy(),
        references=references,
    )


def build_embedding_endpoint_policy() -> EmbeddingEndpointPolicy:
    raw = settings.EMBEDDING_BASE_URL_ALLOWLIST or ""
    return EmbeddingEndpointPolicy(
        allowed_base_urls=tuple(
            value.strip() for value in raw.split(",") if value.strip()
        )
    )
