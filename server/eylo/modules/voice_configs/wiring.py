"""Dependency wiring for voice config services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.voice_configs.resolver import VoiceConfigResolver
from eylo.modules.voice_configs.service import VoiceConfigReferences, VoiceConfigService


def _build_provider_config_service(db: AsyncSession | None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )


def build_voice_config_service(
    db: AsyncSession | None = None,
    *,
    references: VoiceConfigReferences | None = None,
) -> VoiceConfigService:
    return VoiceConfigService(
        _build_provider_config_service(db),
        references,
    )


def build_voice_config_resolver(
    db: AsyncSession | None = None,
) -> VoiceConfigResolver:
    return VoiceConfigResolver(build_voice_config_service(db))
