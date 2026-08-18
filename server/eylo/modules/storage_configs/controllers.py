"""Storage config transport controller."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.masking import mask_secrets
from eylo.modules.storage_configs.catalog import storage_capabilities
from eylo.modules.storage_configs.schemas import (
    StorageCapabilitiesResponse,
    StorageConfigCreate,
    StorageConfigResponse,
    StorageConfigUpdate,
)
from eylo.modules.storage_configs.service import StorageConfigService

__all__ = ["StorageConfigController"]


class StorageConfigController:
    def __init__(self, service: StorageConfigService) -> None:
        self._service = service

    async def create(
        self,
        organization_id: UUID,
        request: StorageConfigCreate,
    ) -> StorageConfigResponse:
        config = await self._service.create(
            organization_id=organization_id,
            provider=request.provider,
            name=request.name,
            config=request.config,
            secrets=request.secrets,
        )
        return self._to_response(config)

    async def list(self, organization_id: UUID) -> list[StorageConfigResponse]:
        configs = await self._service.list(organization_id=organization_id)
        return [self._to_response(config) for config in configs]

    async def get(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> StorageConfigResponse:
        config = await self._service.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        return self._to_response(config)

    async def update(
        self,
        organization_id: UUID,
        config_id: UUID,
        request: StorageConfigUpdate,
    ) -> StorageConfigResponse:
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

    @staticmethod
    def _to_response(config) -> StorageConfigResponse:
        capabilities = storage_capabilities(config.provider)
        return StorageConfigResponse(
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
            capabilities=StorageCapabilitiesResponse(**capabilities),
        )
