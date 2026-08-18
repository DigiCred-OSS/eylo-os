"""Routes for WebRTC configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.webrtc_configs.controllers import WebRTCConfigController
from eylo.modules.webrtc_configs.schemas import (
    WebRTCConfigCreate,
    WebRTCConfigResponse,
    WebRTCConfigUpdate,
    WebRTCConfigVerificationResponse,
)
from eylo.modules.webrtc_configs.verification import WebRTCVerificationError
from eylo.modules.webrtc_configs.wiring import build_webrtc_config_service
from eylo.pipelines.agents.config_deletion import delete_agent_bound_config
from eylo.pipelines.webrtc.config_verification import (
    WebRTCConfigVerificationUseCase,
    WebRTCRuntimeVerifier,
)

router = APIRouter(prefix="/webrtc-configs", tags=["webrtc-configs"])


def _build_controller() -> WebRTCConfigController:
    return WebRTCConfigController(build_webrtc_config_service())


@router.post("", response_model=WebRTCConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_webrtc_config(
    request: WebRTCConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> WebRTCConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[WebRTCConfigResponse])
async def list_webrtc_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[WebRTCConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=WebRTCConfigResponse)
async def get_webrtc_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> WebRTCConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=WebRTCConfigResponse)
async def update_webrtc_config(
    config_id: UUID,
    request: WebRTCConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> WebRTCConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id, config_id, request
        )


@router.post(
    "/{config_id}/verify",
    response_model=WebRTCConfigVerificationResponse,
)
async def verify_webrtc_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> WebRTCConfigVerificationResponse:
    try:
        result = await WebRTCConfigVerificationUseCase(
            WebRTCRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except WebRTCVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WebRTC provider verification failed.",
        ) from None
    return WebRTCConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webrtc_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await delete_agent_bound_config(
        organization_id=current_user.organization_id,
        config_id=config_id,
        capability=Capability.WEBRTC,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
