"""Routes for STT, TTS, and realtime voice provider configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.controllers import VoiceConfigController
from eylo.modules.voice_configs.schemas import (
    VoiceConfigCreate,
    VoiceConfigResponse,
    VoiceConfigUpdate,
    VoiceConfigVerificationResponse,
)
from eylo.modules.voice_configs.verification import VoiceVerificationError
from eylo.modules.voice_configs.wiring import build_voice_config_service
from eylo.pipelines.voice.config_deletion import VoiceConfigDeletionUseCase
from eylo.pipelines.voice.config_verification import (
    VoiceConfigVerificationUseCase,
    VoiceRuntimeVerifier,
)


def _build_controller(kind: VoiceKind) -> VoiceConfigController:
    return VoiceConfigController(build_voice_config_service(), kind)


# STT routes

stt_router = APIRouter(prefix="/stt-configs", tags=["stt-configs"])


@stt_router.post("", response_model=VoiceConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_stt_config(
    request: VoiceConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.STT).create(
            current_user.organization_id, request
        )


@stt_router.get("", response_model=list[VoiceConfigResponse])
async def list_stt_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[VoiceConfigResponse]:
    async with start_transaction():
        return await _build_controller(VoiceKind.STT).list(current_user.organization_id)


@stt_router.get("/{config_id}", response_model=VoiceConfigResponse)
async def get_stt_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.STT).get(
            current_user.organization_id, config_id
        )


@stt_router.patch("/{config_id}", response_model=VoiceConfigResponse)
async def update_stt_config(
    config_id: UUID,
    request: VoiceConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.STT).update(
            current_user.organization_id, config_id, request
        )


@stt_router.post(
    "/{config_id}/verify",
    response_model=VoiceConfigVerificationResponse,
)
async def verify_stt_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigVerificationResponse:
    return await _verify_config(
        current_user.organization_id,
        config_id,
        VoiceKind.STT,
    )


@stt_router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stt_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await VoiceConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
        kind=VoiceKind.STT,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# TTS routes

tts_router = APIRouter(prefix="/tts-configs", tags=["tts-configs"])


@tts_router.post("", response_model=VoiceConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_tts_config(
    request: VoiceConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.TTS).create(
            current_user.organization_id, request
        )


@tts_router.get("", response_model=list[VoiceConfigResponse])
async def list_tts_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[VoiceConfigResponse]:
    async with start_transaction():
        return await _build_controller(VoiceKind.TTS).list(current_user.organization_id)


@tts_router.get("/{config_id}", response_model=VoiceConfigResponse)
async def get_tts_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.TTS).get(
            current_user.organization_id, config_id
        )


@tts_router.patch("/{config_id}", response_model=VoiceConfigResponse)
async def update_tts_config(
    config_id: UUID,
    request: VoiceConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.TTS).update(
            current_user.organization_id, config_id, request
        )


@tts_router.post(
    "/{config_id}/verify",
    response_model=VoiceConfigVerificationResponse,
)
async def verify_tts_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigVerificationResponse:
    return await _verify_config(
        current_user.organization_id,
        config_id,
        VoiceKind.TTS,
    )


@tts_router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tts_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await VoiceConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
        kind=VoiceKind.TTS,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Realtime speech routes

realtime_router = APIRouter(
    prefix="/realtime-configs",
    tags=["realtime-configs"],
)


@realtime_router.post(
    "",
    response_model=VoiceConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_realtime_config(
    request: VoiceConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.REALTIME).create(
            current_user.organization_id,
            request,
        )


@realtime_router.get("", response_model=list[VoiceConfigResponse])
async def list_realtime_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[VoiceConfigResponse]:
    async with start_transaction():
        return await _build_controller(VoiceKind.REALTIME).list(
            current_user.organization_id
        )


@realtime_router.get("/{config_id}", response_model=VoiceConfigResponse)
async def get_realtime_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.REALTIME).get(
            current_user.organization_id,
            config_id,
        )


@realtime_router.patch("/{config_id}", response_model=VoiceConfigResponse)
async def update_realtime_config(
    config_id: UUID,
    request: VoiceConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigResponse:
    async with start_transaction():
        return await _build_controller(VoiceKind.REALTIME).update(
            current_user.organization_id,
            config_id,
            request,
        )


@realtime_router.post(
    "/{config_id}/verify",
    response_model=VoiceConfigVerificationResponse,
)
async def verify_realtime_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> VoiceConfigVerificationResponse:
    return await _verify_config(
        current_user.organization_id,
        config_id,
        VoiceKind.REALTIME,
    )


@realtime_router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_realtime_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await VoiceConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
        kind=VoiceKind.REALTIME,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _verify_config(
    organization_id: UUID,
    config_id: UUID,
    kind: VoiceKind,
) -> VoiceConfigVerificationResponse:
    try:
        result = await VoiceConfigVerificationUseCase(
            VoiceRuntimeVerifier()
        ).verify(
            organization_id=organization_id,
            config_id=config_id,
            kind=kind,
        )
    except VoiceVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Voice provider verification failed.",
        ) from None
    return VoiceConfigVerificationResponse(
        provider=result.provider,
        kind=result.kind.value,
        revision=result.revision,
        verified_at=result.verified_at,
    )
