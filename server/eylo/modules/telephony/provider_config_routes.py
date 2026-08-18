"""Authenticated lifecycle routes for explicit telephony configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.telephony.provider_config_controller import ProviderConfigController
from eylo.modules.telephony.provider_config_verification import (
    TelephonyVerificationError,
)
from eylo.modules.telephony.schemas import (
    ProviderConfigApiResponseSchema,
    ProviderConfigCreateSchema,
    ProviderConfigUpdateSchema,
    ProviderConfigVerificationResponse,
)
from eylo.modules.telephony.wiring import build_telephony_config_service
from eylo.pipelines.telephony.config_deletion import (
    TelephonyConfigDeletionUseCase,
)
from eylo.pipelines.telephony.config_verification import (
    TelephonyConfigVerificationUseCase,
    TelephonyRuntimeVerifier,
)

router = APIRouter(prefix="/telephony-configs", tags=["telephony-configs"])


def _controller() -> ProviderConfigController:
    return ProviderConfigController(build_telephony_config_service())


@router.post(
    "",
    response_model=ProviderConfigApiResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_telephony_config(
    request: ProviderConfigCreateSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> ProviderConfigApiResponseSchema:
    async with start_transaction():
        return await _controller().create(current_user.organization_id, request)


@router.get("", response_model=list[ProviderConfigApiResponseSchema])
async def list_telephony_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[ProviderConfigApiResponseSchema]:
    async with start_transaction(ro=True):
        return await _controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=ProviderConfigApiResponseSchema)
async def get_telephony_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> ProviderConfigApiResponseSchema:
    async with start_transaction(ro=True):
        return await _controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=ProviderConfigApiResponseSchema)
async def update_telephony_config(
    config_id: UUID,
    request: ProviderConfigUpdateSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> ProviderConfigApiResponseSchema:
    async with start_transaction():
        return await _controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=ProviderConfigVerificationResponse,
)
async def verify_telephony_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> ProviderConfigVerificationResponse:
    try:
        result = await TelephonyConfigVerificationUseCase(
            TelephonyRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except TelephonyVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telephony provider verification failed.",
        ) from None
    return ProviderConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_telephony_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await TelephonyConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
