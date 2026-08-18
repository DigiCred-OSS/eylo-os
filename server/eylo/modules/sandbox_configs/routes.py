"""Routes for explicit organization-owned sandbox configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.sandbox_configs.controllers import SandboxConfigController
from eylo.modules.sandbox_configs.schemas import (
    SandboxConfigCreate,
    SandboxConfigResponse,
    SandboxConfigUpdate,
    SandboxConfigVerificationResponse,
)
from eylo.modules.sandbox_configs.verification import SandboxVerificationError
from eylo.modules.sandbox_configs.wiring import build_sandbox_config_service
from eylo.pipelines.sandbox.config_deletion import SandboxConfigDeletionUseCase
from eylo.pipelines.sandbox.config_verification import (
    SandboxConfigVerificationUseCase,
    SandboxRuntimeVerifier,
)

router = APIRouter(prefix="/sandbox-configs", tags=["sandbox-configs"])


def _build_controller() -> SandboxConfigController:
    return SandboxConfigController(build_sandbox_config_service())


@router.post("", response_model=SandboxConfigResponse, status_code=201)
async def create_sandbox_config(
    request: SandboxConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> SandboxConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[SandboxConfigResponse])
async def list_sandbox_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[SandboxConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=SandboxConfigResponse)
async def get_sandbox_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> SandboxConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=SandboxConfigResponse)
async def update_sandbox_config(
    config_id: UUID,
    request: SandboxConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> SandboxConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=SandboxConfigVerificationResponse,
)
async def verify_sandbox_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> SandboxConfigVerificationResponse:
    try:
        result = await SandboxConfigVerificationUseCase(
            SandboxRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except SandboxVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Sandbox provider verification failed.",
        ) from None
    return SandboxConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await SandboxConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
