"""API routes for telephony management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.telephony.controllers import PhoneNumberController
from eylo.modules.telephony.schemas import (
    PhoneNumberApiResponseSchema,
    PhoneNumberCreateSchema,
    PhoneNumberUpdateSchema,
    PhoneNumbersPaginated,
)
from eylo.modules.telephony.wiring import build_telephony_config_resolver

from .constants import APP_TAG

router = APIRouter(prefix="/phone-numbers", tags=[APP_TAG])


@router.get("", response_model=PhoneNumbersPaginated)
async def list_phone_numbers(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    current_user: CurrentUserSchema = Depends(get_current_user),
    provider: str | None = None,
) -> PhoneNumbersPaginated:
    async with start_transaction(ro=True):
        return await PhoneNumberController().list(
            current_user.organization_id,
            pagination,
            provider=provider,
        )


@router.post("", response_model=PhoneNumberApiResponseSchema, status_code=201)
async def create_phone_number(
    request: PhoneNumberCreateSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> PhoneNumberApiResponseSchema:
    async with start_transaction():
        resolved = await build_telephony_config_resolver().resolve(
            current_user.organization_id,
            provider_config_id=request.provider_config_id,
        )
        if (
            request.provider != resolved.provider.value
            or request.provider_config_revision != resolved.provider_config_revision
        ):
            raise HTTPException(
                status_code=422,
                detail="Phone number authority must match the current ready config revision.",
            )
        return await PhoneNumberController().create(
            current_user.organization_id,
            request,
        )


@router.get("/{phone_number_id}", response_model=PhoneNumberApiResponseSchema)
async def get_phone_number(
    phone_number_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> PhoneNumberApiResponseSchema:
    async with start_transaction(ro=True):
        return await PhoneNumberController().get(
            phone_number_id,
            current_user.organization_id,
        )


@router.patch("/{phone_number_id}", response_model=PhoneNumberApiResponseSchema)
async def update_phone_number(
    phone_number_id: UUID,
    request: PhoneNumberUpdateSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> PhoneNumberApiResponseSchema:
    async with start_transaction():
        return await PhoneNumberController().update(
            phone_number_id,
            request,
            current_user.organization_id,
        )


@router.delete("/{phone_number_id}", response_model=PhoneNumberApiResponseSchema)
async def delete_phone_number(
    phone_number_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> PhoneNumberApiResponseSchema:
    async with start_transaction():
        return await PhoneNumberController().delete(
            phone_number_id,
            current_user.organization_id,
        )
