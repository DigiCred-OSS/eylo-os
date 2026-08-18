"""WebRTC config transport controller."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.masking import mask_secrets
from eylo.modules.webrtc_configs.schemas import (
    WebRTCConfigCreate,
    WebRTCConfigResponse,
    WebRTCConfigUpdate,
)
from eylo.modules.webrtc_configs.service import WebRTCConfigService

__all__ = ["WebRTCConfigController"]


class WebRTCConfigController:
    def __init__(self, service: WebRTCConfigService) -> None:
        self._service = service

    async def create(
        self,
        organization_id: UUID,
        request: WebRTCConfigCreate,
    ) -> WebRTCConfigResponse:
        config = await self._service.create(
            organization_id=organization_id,
            provider=request.provider,
            name=request.name,
            config=request.config,
            secrets=request.secrets,
        )
        return self._to_response(config)

    async def list(self, organization_id: UUID) -> list[WebRTCConfigResponse]:
        configs = await self._service.list(organization_id=organization_id)
        return [self._to_response(config) for config in configs]

    async def get(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> WebRTCConfigResponse:
        config = await self._service.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        return self._to_response(config)

    async def update(
        self,
        organization_id: UUID,
        config_id: UUID,
        request: WebRTCConfigUpdate,
    ) -> WebRTCConfigResponse:
        config = await self._service.update(
            organization_id=organization_id,
            config_id=config_id,
            name=request.name if "name" in request.model_fields_set else None,
            config=request.config if "config" in request.model_fields_set else None,
            secret_patch=(
                request.secrets if "secrets" in request.model_fields_set else None
            ),
            enabled=(
                request.enabled if "enabled" in request.model_fields_set else None
            ),
        )
        return self._to_response(config)

    async def delete(self, organization_id: UUID, config_id: UUID) -> None:
        await self._service.delete(
            organization_id=organization_id,
            config_id=config_id,
        )

    @staticmethod
    def _to_response(config) -> WebRTCConfigResponse:
        return WebRTCConfigResponse(
            id=config.id,
            provider=config.provider,
            name=config.name,
            revision=config.revision,
            enabled=config.enabled,
            configured=config.configured,
            verified=config.verified,
            ready=config.ready,
            verified_at=config.verified_at,
            config=dict(config.config),
            secrets=mask_secrets(config.secrets),
        )
