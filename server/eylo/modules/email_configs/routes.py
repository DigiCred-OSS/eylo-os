"""Routes for email configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.email_configs.controllers import EmailConfigController
from eylo.modules.email_configs.schemas import (
    EmailConfigCreate,
    EmailConfigResponse,
    EmailConfigUpdate,
    EmailConfigVerificationResponse,
)
from eylo.modules.email_configs.verification import EmailVerificationError
from eylo.modules.email_configs.wiring import build_email_config_service
from eylo.modules.provider_configs.constants import Capability
from eylo.pipelines.agents.config_deletion import delete_agent_bound_config
from eylo.pipelines.email.config_verification import (
    EmailConfigVerificationUseCase,
    EmailRuntimeVerifier,
)

router = APIRouter(prefix="/email-configs", tags=["email-configs"])


def _build_controller() -> EmailConfigController:
    return EmailConfigController(build_email_config_service())


@router.post("", response_model=EmailConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_email_config(
    request: EmailConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmailConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[EmailConfigResponse])
async def list_email_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[EmailConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=EmailConfigResponse)
async def get_email_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmailConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=EmailConfigResponse)
async def update_email_config(
    config_id: UUID,
    request: EmailConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmailConfigResponse:
    async with start_transaction():
        return await _build_controller().update(current_user.organization_id, config_id, request)


@router.post(
    "/{config_id}/verify",
    response_model=EmailConfigVerificationResponse,
)
async def verify_email_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EmailConfigVerificationResponse:
    try:
        result = await EmailConfigVerificationUseCase(
            EmailRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except EmailVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email provider verification failed.",
        ) from None
    return EmailConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await delete_agent_bound_config(
        organization_id=current_user.organization_id,
        config_id=config_id,
        capability=Capability.EMAIL,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
