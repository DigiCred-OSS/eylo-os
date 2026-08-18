"""Voice config controller — maps transport schemas to service calls."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.masking import mask_secrets
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.schemas import (
    VoiceConfigCreate,
    VoiceConfigResponse,
    VoiceConfigUpdate,
)
from eylo.modules.voice_configs.service import VoiceConfigService

__all__ = ["VoiceConfigController"]


class VoiceConfigController:
    def __init__(self, service: VoiceConfigService, kind: VoiceKind) -> None:
        self._service = service
        self._kind = kind

    async def create(
        self,
        organization_id: UUID,
        request: VoiceConfigCreate,
    ) -> VoiceConfigResponse:
        config = await self._service.create(
            organization_id=organization_id,
            kind=self._kind,
            provider=request.provider,
            name=request.name,
            config=request.config,
            secrets=request.secrets,
        )
        return self._to_response(config)

    async def list(self, organization_id: UUID) -> list[VoiceConfigResponse]:
        configs = await self._service.list(
            organization_id=organization_id,
            kind=self._kind,
        )
        return [self._to_response(c) for c in configs]

    async def get(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> VoiceConfigResponse:
        config = await self._service.get(
            organization_id=organization_id,
            config_id=config_id,
            kind=self._kind,
        )
        return self._to_response(config)

    async def update(
        self,
        organization_id: UUID,
        config_id: UUID,
        request: VoiceConfigUpdate,
    ) -> VoiceConfigResponse:
        config = await self._service.update(
            organization_id=organization_id,
            config_id=config_id,
            kind=self._kind,
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

    async def delete(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        await self._service.delete(
            organization_id=organization_id,
            config_id=config_id,
            kind=self._kind,
        )

    def _to_response(self, config) -> VoiceConfigResponse:
        kind_value = self._kind.value
        return VoiceConfigResponse(
            id=config.id,
            provider=config.provider,
            kind=kind_value,
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
