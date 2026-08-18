"""Authenticated provider-onboarding catalog routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.provider_onboarding.catalog import get_provider_onboarding_catalog
from eylo.modules.provider_onboarding.schemas import (
    ProviderOnboardingCatalogResponse,
)

router = APIRouter(prefix="/provider-onboarding", tags=["provider-onboarding"])


@router.get("/catalog", response_model=ProviderOnboardingCatalogResponse)
async def get_catalog(
    _current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> ProviderOnboardingCatalogResponse:
    """Return the complete provider form contract for an authenticated member."""
    return get_provider_onboarding_catalog()
