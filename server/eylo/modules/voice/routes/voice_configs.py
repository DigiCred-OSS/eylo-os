"""Private organization Voice Config routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.voice.controllers.voice_configs import VoiceConfigController
from eylo.modules.voice.schemas.api import (
    OrganizationVoiceConfigCreate,
    OrganizationVoiceConfigUpdate,
    VoiceConfigCompatibilityRead,
    VoiceConfigRead,
)

router = APIRouter(prefix="/{organization_id}/voice-configs", tags=[APP_TAG])


@router.get("", response_model=list[VoiceConfigRead])
async def list_voice_configs(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> list[VoiceConfigRead]:
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True) as db:
        return await VoiceConfigController(db).list(organization_id)


@router.post("", response_model=VoiceConfigRead, status_code=status.HTTP_201_CREATED)
async def create_voice_config(
    organization_id: UUID,
    payload: OrganizationVoiceConfigCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> VoiceConfigRead:
    _authorize(organization_id, current_user)
    async with start_transaction() as db:
        return await VoiceConfigController(db).create(
            organization_id=organization_id,
            payload=payload,
        )


@router.get("/{voice_config_id}", response_model=VoiceConfigRead)
async def get_voice_config(
    organization_id: UUID,
    voice_config_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> VoiceConfigRead:
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True) as db:
        return await VoiceConfigController(db).get(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )


@router.patch("/{voice_config_id}", response_model=VoiceConfigRead)
async def update_voice_config(
    organization_id: UUID,
    voice_config_id: UUID,
    payload: OrganizationVoiceConfigUpdate,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> VoiceConfigRead:
    _authorize(organization_id, current_user)
    async with start_transaction() as db:
        return await VoiceConfigController(db).update(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            payload=payload,
        )


@router.get(
    "/{voice_config_id}/compatibility",
    response_model=VoiceConfigCompatibilityRead,
)
async def get_voice_config_compatibility(
    organization_id: UUID,
    voice_config_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> VoiceConfigCompatibilityRead:
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True) as db:
        return await VoiceConfigController(db).compatibility(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )


@router.patch("/{voice_config_id}/sections/{section}", response_model=VoiceConfigRead)
async def patch_voice_config_section(
    organization_id: UUID,
    voice_config_id: UUID,
    section: str,
    data: dict[str, Any] | list[dict[str, Any]],
    expected_revision: int = Query(..., gt=0),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> VoiceConfigRead:
    _authorize(organization_id, current_user)
    async with start_transaction() as db:
        return await VoiceConfigController(db).patch_section(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            section=section,
            data=data,
            expected_revision=expected_revision,
        )


@router.delete("/{voice_config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_config(
    organization_id: UUID,
    voice_config_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> Response:
    _authorize(organization_id, current_user)
    async with start_transaction() as db:
        await VoiceConfigController(db).delete(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


__all__ = ["router"]
