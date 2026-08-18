"""Dependency wiring for WebRTC config services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository
from eylo.modules.provider_configs.service import ProviderConfigService
from eylo.modules.webrtc_configs.resolver import WebRTCConfigResolver
from eylo.modules.webrtc_configs.service import WebRTCConfigService


def _build_provider_config_service(db: AsyncSession | None) -> ProviderConfigService:
    session = db if db is not None else get_transaction()
    return ProviderConfigService(
        ProviderConfigRepository(session, get_secret_cipher())
    )


def build_webrtc_config_service(
    db: AsyncSession | None = None,
    *,
    references=None,
) -> WebRTCConfigService:
    return WebRTCConfigService(
        _build_provider_config_service(db),
        references=references,
    )


def build_webrtc_config_resolver(db: AsyncSession | None = None) -> WebRTCConfigResolver:
    return WebRTCConfigResolver(build_webrtc_config_service(db))
