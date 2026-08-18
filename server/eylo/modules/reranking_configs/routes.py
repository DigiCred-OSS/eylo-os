"""Routes for organization-owned reranking configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.reranking_configs.controllers import RerankingConfigController
from eylo.modules.reranking_configs.schemas import (
    RerankingConfigCreate,
    RerankingConfigResponse,
    RerankingConfigUpdate,
    RerankingConfigVerificationResponse,
)
from eylo.modules.reranking_configs.verification import RerankingVerificationError
from eylo.modules.reranking_configs.wiring import build_reranking_config_service
from eylo.pipelines.reranking.config_deletion import RerankingConfigDeletionUseCase
from eylo.pipelines.reranking.config_verification import (
    RerankingConfigVerificationUseCase,
    RerankingRuntimeVerifier,
)

router = APIRouter(prefix="/reranking-configs", tags=["reranking-configs"])


def _build_controller() -> RerankingConfigController:
    return RerankingConfigController(build_reranking_config_service())


@router.post("", response_model=RerankingConfigResponse, status_code=201)
async def create_reranking_config(
    request: RerankingConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> RerankingConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[RerankingConfigResponse])
async def list_reranking_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[RerankingConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=RerankingConfigResponse)
async def get_reranking_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> RerankingConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=RerankingConfigResponse)
async def update_reranking_config(
    config_id: UUID,
    request: RerankingConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> RerankingConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=RerankingConfigVerificationResponse,
)
async def verify_reranking_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> RerankingConfigVerificationResponse:
    try:
        result = await RerankingConfigVerificationUseCase(
            RerankingRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except RerankingVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None
    return RerankingConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reranking_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await RerankingConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
