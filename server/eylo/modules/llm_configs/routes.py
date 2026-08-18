"""HTTP routes for the `llm_configs` domain."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.llm_configs.controllers import LLMConfigController
from eylo.modules.llm_configs.schemas import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigUpdate,
    LLMConfigVerificationResponse,
)
from eylo.modules.llm_configs.verification import (
    LLMConfigVerificationService,
    LLMCredentialVerifier,
)
from eylo.modules.llm_configs.wiring import build_llm_config_service
from eylo.modules.provider_configs.constants import Capability
from eylo.pipelines.agents.config_deletion import delete_agent_bound_config

router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])


async def get_llm_config_controller() -> AsyncIterator[LLMConfigController]:
    async with start_transaction():
        service = build_llm_config_service()
        yield LLMConfigController(
            service,
            LLMConfigVerificationService(service, LLMCredentialVerifier()),
        )


@router.post(
    "",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_llm_config(
    request: LLMConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        LLMConfigController,
        Depends(get_llm_config_controller, scope="function"),
    ],
) -> LLMConfigResponse:
    return await controller.create(current_user.organization_id, request)


@router.get("", response_model=list[LLMConfigResponse])
async def list_llm_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        LLMConfigController,
        Depends(get_llm_config_controller, scope="function"),
    ],
) -> list[LLMConfigResponse]:
    return await controller.list(current_user.organization_id)


@router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        LLMConfigController,
        Depends(get_llm_config_controller, scope="function"),
    ],
) -> LLMConfigResponse:
    return await controller.get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: UUID,
    request: LLMConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        LLMConfigController,
        Depends(get_llm_config_controller, scope="function"),
    ],
) -> LLMConfigResponse:
    return await controller.update(current_user.organization_id, config_id, request)


@router.post(
    "/{config_id}/verify",
    response_model=LLMConfigVerificationResponse,
)
async def verify_llm_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        LLMConfigController,
        Depends(get_llm_config_controller, scope="function"),
    ],
) -> LLMConfigVerificationResponse:
    return await controller.verify(current_user.organization_id, config_id)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await delete_agent_bound_config(
        organization_id=current_user.organization_id,
        config_id=config_id,
        capability=Capability.LLM,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
