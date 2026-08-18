"""Routes for explicit organization-owned memory configs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from eylo.common.contracts.memory import MemoryError
from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.memory.schemas import (
    MemoryEmbeddingSpaceRead,
    MemoryReindexJobRead,
    MemoryReindexStatusRead,
)
from eylo.modules.memory_configs.controllers import MemoryConfigController
from eylo.modules.memory_configs.domain import InvalidMemoryConfig
from eylo.modules.memory_configs.schemas import (
    MemoryConfigCreate,
    MemoryConfigResponse,
    MemoryConfigUpdate,
    MemoryConfigVerificationResponse,
)
from eylo.modules.memory_configs.verification import MemoryVerificationError
from eylo.modules.memory_configs.wiring import build_memory_config_service
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.memory.config_deletion import MemoryConfigDeletionUseCase
from eylo.pipelines.memory.config_verification import (
    MemoryConfigVerificationUseCase,
    MemoryRuntimeVerifier,
)
from eylo.pipelines.memory.reindex import (
    inspect_memory_reindex,
    request_memory_reindex,
)

router = APIRouter(prefix="/memory-configs", tags=["memory-configs"])


def _build_controller() -> MemoryConfigController:
    return MemoryConfigController(build_memory_config_service())


@router.post("", response_model=MemoryConfigResponse, status_code=201)
async def create_memory_config(
    request: MemoryConfigCreate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> MemoryConfigResponse:
    async with start_transaction():
        return await _build_controller().create(current_user.organization_id, request)


@router.get("", response_model=list[MemoryConfigResponse])
async def list_memory_configs(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[MemoryConfigResponse]:
    async with start_transaction():
        return await _build_controller().list(current_user.organization_id)


@router.get("/{config_id}", response_model=MemoryConfigResponse)
async def get_memory_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> MemoryConfigResponse:
    async with start_transaction():
        return await _build_controller().get(current_user.organization_id, config_id)


@router.patch("/{config_id}", response_model=MemoryConfigResponse)
async def update_memory_config(
    config_id: UUID,
    request: MemoryConfigUpdate,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> MemoryConfigResponse:
    async with start_transaction():
        return await _build_controller().update(
            current_user.organization_id,
            config_id,
            request,
        )


@router.post(
    "/{config_id}/verify",
    response_model=MemoryConfigVerificationResponse,
)
async def verify_memory_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> MemoryConfigVerificationResponse:
    try:
        result = await MemoryConfigVerificationUseCase(
            MemoryRuntimeVerifier()
        ).verify(
            organization_id=current_user.organization_id,
            config_id=config_id,
        )
    except MemoryVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory provider verification failed.",
        ) from None
    return MemoryConfigVerificationResponse(
        provider=result.provider,
        revision=result.revision,
        verified_at=result.verified_at,
    )


@router.get(
    "/{config_id}/reindex",
    response_model=MemoryReindexStatusRead,
)
async def get_memory_reindex_status(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    ) -> MemoryReindexStatusRead:
    inspection = await inspect_memory_reindex(
        organization_id=current_user.organization_id,
        memory_provider_config_id=config_id,
    )
    active = inspection.active_space
    target = inspection.target_space
    available = inspection.available_space
    return MemoryReindexStatusRead(
        initialized=inspection.index is not None,
        state=None if inspection.index is None else inspection.index.reindex_state,
        active_space=_embedding_space_read(active),
        target_space=_embedding_space_read(target),
        available_space=_embedding_space_read(available),
        update_available=(
            active is not None
            and (
                (target is not None and not active.is_compatible_with(target))
                or (
                    available is not None
                    and not active.is_compatible_with(available)
                )
            )
        ),
        last_error=(
            None if inspection.index is None else inspection.index.reindex_last_error
        ),
        latest_job=inspection.latest_job,
    )


@router.post(
    "/{config_id}/reindex",
    response_model=MemoryReindexJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_memory_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> MemoryReindexJobRead:
    try:
        return await request_memory_reindex(
            organization_id=current_user.organization_id,
            memory_provider_config_id=config_id,
        )
    except MemoryError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (InvalidEmbeddingConfig, InvalidMemoryConfig, NotConfiguredError):
        raise HTTPException(
            status_code=409,
            detail="Verify the bound embedding configuration before reindexing.",
        ) from None


def _embedding_space_read(space) -> MemoryEmbeddingSpaceRead | None:
    if space is None:
        return None
    return MemoryEmbeddingSpaceRead(
        provider_config_id=space.provider_config_id,
        provider_config_revision=space.provider_config_revision,
        provider=space.provider,
        model=space.model,
        dimensions=space.dimensions,
        space_id=space.id,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_config(
    config_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Response:
    await MemoryConfigDeletionUseCase().delete(
        organization_id=current_user.organization_id,
        config_id=config_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
