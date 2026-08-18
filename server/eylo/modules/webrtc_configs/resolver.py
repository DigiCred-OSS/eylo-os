"""Resolve one explicit organization WebRTC config."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.webrtc_configs.domain import InvalidWebRTCConfig, ResolvedWebRTC
from eylo.modules.webrtc_configs.service import WebRTCConfigService

__all__ = ["WebRTCConfigResolver"]


class WebRTCConfigResolver:
    def __init__(self, configs: WebRTCConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedWebRTC:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        provider_config = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        try:
            return ResolvedWebRTC.from_provider_config(
                provider_config_id=provider_config.provider_config_id,
                organization_id=organization_id,
                provider_config=provider_config,
            )
        except InvalidWebRTCConfig:
            raise _not_configured("valid_provider_config") from None

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedWebRTC:
        provider_config = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        try:
            return ResolvedWebRTC.from_provider_config(
                provider_config_id=provider_config.provider_config_id,
                organization_id=organization_id,
                provider_config=provider_config,
            )
        except InvalidWebRTCConfig:
            raise _not_configured("valid_pinned_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.WEBRTC,
        missing=[missing],
        configure_via="/api/webrtc-configs",
    )
