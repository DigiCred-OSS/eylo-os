"""Application dependency wiring for organization-scoped LLM configuration."""

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.service import LLMConfigService
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService


def build_llm_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
) -> LLMConfigService:
    """Build an LLM config service for an explicit or active transaction."""
    session = db if db is not None else get_transaction()
    provider_configs = ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )
    return LLMConfigService(provider_configs, references=references)


def build_llm_config_resolver(
    db: AsyncSession | None = None,
) -> LLMConfigResolver:
    """Build an LLM resolver for an explicit or active transaction."""
    return LLMConfigResolver(build_llm_config_service(db))
