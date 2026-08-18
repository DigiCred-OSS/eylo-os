"""HTTP translation for organization-owned Voice Configs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.voice.exceptions import (
    RealtimeVoiceDisabledError,
    VoiceConfigConflict,
    VoiceConfigInUse,
    VoiceConfigNotFound,
)
from eylo.modules.voice.schemas.api import (
    OrganizationVoiceConfigCreate,
    OrganizationVoiceConfigUpdate,
    VoiceConfigCompatibilityRead,
    VoiceConfigRead,
)
from eylo.pipelines.voice.capabilities import VoiceCapabilityService
from eylo.pipelines.voice.configuration import VoiceConfigurationService


class VoiceConfigController:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self.service = VoiceConfigurationService(db)

    async def list(self, organization_id: UUID) -> list[VoiceConfigRead]:
        return await self.service.list(organization_id)

    async def get(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> VoiceConfigRead:
        try:
            return await self.service.get(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    async def compatibility(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> VoiceConfigCompatibilityRead:
        try:
            return await VoiceCapabilityService(self._db).get(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    async def create(
        self,
        *,
        organization_id: UUID,
        payload: OrganizationVoiceConfigCreate,
    ) -> VoiceConfigRead:
        try:
            return await self.service.create(
                organization_id=organization_id,
                payload=payload,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except VoiceConfigConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="A Voice Config with this name already exists.",
            ) from error
        except RealtimeVoiceDisabledError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def update(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        payload: OrganizationVoiceConfigUpdate,
    ) -> VoiceConfigRead:
        try:
            return await self.service.update(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
                payload=payload,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except VoiceConfigConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="A Voice Config with this name already exists.",
            ) from error
        except RealtimeVoiceDisabledError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def patch_section(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        section: str,
        data: Any,
        expected_revision: int,
    ) -> VoiceConfigRead:
        try:
            return await self.service.patch_section(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
                section=section,
                data=data,
                expected_revision=expected_revision,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except VoiceConfigConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RealtimeVoiceDisabledError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def delete(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> None:
        try:
            await self.service.delete(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
            )
        except VoiceConfigNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except VoiceConfigInUse as error:
            raise HTTPException(status_code=409, detail=str(error)) from error


__all__ = ["VoiceConfigController"]
