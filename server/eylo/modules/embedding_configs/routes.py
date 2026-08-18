"""Routes for organization-owned embedding configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.embedding_configs.controllers import EmbeddingConfigController
from eylo.modules.embedding_configs.schemas import (
    EmbeddingConfigCreate,
    EmbeddingConfigResponse,
    EmbeddingConfigUpdate,
    EmbeddingConfigVerificationResponse,
)
from eylo.modules.embedding_configs.verification import EmbeddingVerificationError
from eylo.modules.embedding_configs.wiring import build_embedding_config_service
from eylo.pipelines.embedding.config_deletion import EmbeddingConfigDeletionUseCase
from eylo.pipelines.embedding.config_verification import (
    EmbeddingConfigVerificationUseCase,
    EmbeddingRuntimeVerifier,
)

router = APIRouter(prefix="/embedding-configs", tags=["embedding-configs"])


def _build_controller() -> EmbeddingConfigController:
    return EmbeddingConfigController(build_embedding_config_service())


@router.post("", response_model=EmbeddingConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_embedding_config(
    request: EmbeddingConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmbeddingConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[EmbeddingConfigResponse])
async def list_embedding_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[EmbeddingConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=EmbeddingConfigResponse)
async def get_embedding_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmbeddingConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=EmbeddingConfigResponse)
async def update_embedding_config(
    config_id: UUID,
    request: EmbeddingConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmbeddingConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=EmbeddingConfigVerificationResponse,
)
async def verify_embedding_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmbeddingConfigVerificationResponse:
    try:
        result = await EmbeddingConfigVerificationUseCase(
            EmbeddingRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except EmbeddingVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None
    return EmbeddingConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        dimensions=result.dimensions,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embedding_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await EmbeddingConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
