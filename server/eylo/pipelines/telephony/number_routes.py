"""API routes for searching and purchasing phone numbers from providers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.telephony.constants import APP_TAG
from eylo.modules.telephony.schemas import (
    AvailableNumbersResponseSchema,
    NumberPurchaseRequest,
    NumberSearchParams,
    NumberType,
    PhoneNumberApiResponseSchema,
)
from eylo.pipelines.telephony.number_management import NumberManagementController

router = APIRouter(
    prefix="/telephony-configs/{provider_config_id}/numbers",
    tags=[APP_TAG],
)


@router.get("/available", response_model=AvailableNumbersResponseSchema)
async def search_available_numbers(
    provider_config_id: UUID,
    country: str = Query(
        ...,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Za-z]{2}$",
        description="ISO 3166-1 alpha-2 country code",
    ),
    number_type: NumberType = Query(NumberType.LOCAL, alias="numberType"),
    area_code: str | None = Query(None, alias="areaCode"),
    contains: str | None = Query(None),
    limit: int = Query(20, ge=1, le=30),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AvailableNumbersResponseSchema:
    """Search for available phone numbers from a telephony provider."""
    params = NumberSearchParams(
        country=country,
        number_type=number_type,
        area_code=area_code,
        contains=contains,
        limit=limit,
    )

    return await NumberManagementController().search_available_numbers(
        current_user.organization_id,
        provider_config_id,
        params,
    )


@router.post("/purchase", response_model=PhoneNumberApiResponseSchema, status_code=201)
async def purchase_number(
    provider_config_id: UUID,
    request: NumberPurchaseRequest,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> PhoneNumberApiResponseSchema:
    """Persist a stable intent before one exact charged carrier purchase."""
    return await NumberManagementController().purchase_number(
        organization_id=current_user.organization_id,
        provider_config_id=provider_config_id,
        request=request,
        idempotency_key=idempotency_key,
    )
