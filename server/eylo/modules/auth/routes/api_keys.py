"""HTTP routes for the `auth` domain."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from eylo.common.database import start_transaction
from eylo.modules.auth.controllers.api_key_controller import ApiKeyController
from eylo.modules.auth.schemas import (
    ApiKeyCreate,
    ApiKeyInDb,
    ApiKeyResponse,
    CurrentUserSchema,
)
from eylo.modules.auth.services.auth_service import get_current_user

router = APIRouter(tags=["api-keys"], prefix="/auth")


@router.post(
    "/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    request: ApiKeyCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> ApiKeyResponse:
    """Create API Key."""
    async with start_transaction():
        return await ApiKeyController().create_api_key(
            current_user.organization_id, request
        )


@router.get("/api-keys", response_model=List[ApiKeyInDb])
async def list_api_keys(
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> List[ApiKeyInDb]:
    """List API Keys."""
    async with start_transaction(ro=True):
        return await ApiKeyController().list_api_keys(current_user.organization_id)


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> None:
    """Revoke API Key."""
    async with start_transaction():
        await ApiKeyController().delete_api_key(
            api_key_id,
            current_user.organization_id,
        )
