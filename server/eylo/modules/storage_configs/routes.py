"""Routes for organization-owned storage configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.storage_configs.controllers import StorageConfigController
from eylo.modules.storage_configs.schemas import (
    StorageCapabilitiesResponse,
    StorageConfigCreate,
    StorageConfigResponse,
    StorageConfigUpdate,
    StorageConfigVerificationResponse,
)
from eylo.modules.storage_configs.verification import StorageVerificationError
from eylo.modules.storage_configs.wiring import build_storage_config_service
from eylo.pipelines.storage.config_deletion import StorageConfigDeletionUseCase
from eylo.pipelines.storage.config_verification import (
    StorageConfigVerificationUseCase,
    StorageRuntimeVerifier,
)

router = APIRouter(prefix="/storage-configs", tags=["storage-configs"])


def _build_controller() -> StorageConfigController:
    return StorageConfigController(build_storage_config_service())


@router.post("", response_model=StorageConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_storage_config(
    request: StorageConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> StorageConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[StorageConfigResponse])
async def list_storage_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[StorageConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=StorageConfigResponse)
async def get_storage_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> StorageConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=StorageConfigResponse)
async def update_storage_config(
    config_id: UUID,
    request: StorageConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> StorageConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=StorageConfigVerificationResponse,
)
async def verify_storage_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> StorageConfigVerificationResponse:
    try:
        result = await StorageConfigVerificationUseCase(
            StorageRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except StorageVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage provider verification failed.",
        ) from None
    return StorageConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
        capabilities=StorageCapabilitiesResponse(**result.capabilities.to_dict()),
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storage_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await StorageConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
