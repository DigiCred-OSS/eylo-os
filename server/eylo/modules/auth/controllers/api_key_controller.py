"""Transport orchestration for the `auth` domain."""

from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from eylo.common.database import get_transaction
from eylo.common.exceptions import EntityNotFound
from eylo.modules.auth.schemas import (
    ApiKeyCreate,
    ApiKeyInDb,
    ApiKeyResponse,
)
from eylo.modules.auth.services.api_key_service import ApiKeyService


class ApiKeyController:
    """Controller for API Key management endpoints."""

    def __init__(self):
        self.db_session = get_transaction()
        self.service = ApiKeyService(self.db_session)

    async def create_api_key(
        self, organization_id: UUID, data: ApiKeyCreate
    ) -> ApiKeyResponse:
        """Create a new API Key for an organization."""
        return await self.service.create_api_key(organization_id, data)

    async def list_api_keys(self, organization_id: UUID) -> List[ApiKeyInDb]:
        """List all active API Keys for an organization."""
        return await self.service.list_api_keys(organization_id)

    async def delete_api_key(self, api_key_id: UUID, organization_id: UUID) -> None:
        """Revoke an API Key."""
        try:
            await self.service.delete_api_key(api_key_id, organization_id)
        except EntityNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            ) from error
