"""Build reranking config services from organization-scoped persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.config import settings
from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.reranking_configs.domain import RerankingEndpointPolicy
from eylo.modules.reranking_configs.resolver import RerankingConfigResolver


def _provider_config_service(db: AsyncSession | None = None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(ProviderConfigRepository(session, get_secret_cipher()))


def build_reranking_config_resolver(
    db: AsyncSession | None = None,
) -> RerankingConfigResolver:
    return RerankingConfigResolver(build_reranking_config_service(db))


def build_reranking_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
):
    from eylo.modules.reranking_configs.service import RerankingConfigService

    return RerankingConfigService(
        _provider_config_service(db),
        endpoint_policy=build_reranking_endpoint_policy(),
        references=references,
    )


def build_reranking_endpoint_policy() -> RerankingEndpointPolicy:
    raw = settings.RERANKING_BASE_URL_ALLOWLIST or ""
    return RerankingEndpointPolicy(
        allowed_base_urls=tuple(
            value.strip() for value in raw.split(",") if value.strip()
        )
    )
