"""Application services for the `auth` domain."""

import hashlib
import secrets
from typing import List, Optional, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.exceptions import EntityNotFound
from eylo.common.services import EyloBaseService
from eylo.modules.auth.repository import ApiKeyRepository
from eylo.modules.auth.schemas import (
    ApiKeyCreate,
    ApiKeyInDb,
    ApiKeyResponse,
)


class ApiKeyService(EyloBaseService[ApiKeyInDb]):
    """API Key Service."""

    def __init__(self, db: AsyncSession):
        """Initialize the API key service.

        Args:
            db: Database session for data access operations

        """
        self.db = db
        self._repository = ApiKeyRepository(db)

    @property
    def schema(self) -> Type[ApiKeyInDb]:
        """Returns the ApiKeyInDb schema."""
        return ApiKeyInDb

    @property
    def repository(self) -> ApiKeyRepository:
        """Returns the ApiKeyRepository instance."""
        return self._repository

    def _generate_raw_key(self) -> str:
        """Generate a cryptographically secure random string for the API key."""
        return secrets.token_urlsafe(32)

    def _hash_key(self, raw_key: str) -> str:
        """Generate a SHA-256 hash of the raw API key."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def create_api_key(
        self, organization_id: UUID, data: ApiKeyCreate
    ) -> ApiKeyResponse:
        """Create a new API key for an organization.

        The raw key is generated, hashed, and only the hash is stored.
        The raw key is returned in the response exactly once.

        Args:
            organization_id: The ID of the organization owning the key
            data: The key configuration (name, state and expiration)

        Returns:
            The created API key details including the raw key string

        """
        raw_token = self._generate_raw_key()
        prefix = "eylo_pk_"
        full_raw_key = f"{prefix}{raw_token}"
        hashed_key = self._hash_key(full_raw_key)

        # Use first 8 chars of token as prefix for identification (eylo_pk_ + 4 chars)
        key_prefix = full_raw_key[:12] + "..."

        api_key_model = await self.repository.create_(
            data=data,
            organization_id=organization_id,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )

        response_data = self.orm_to_schema(api_key_model)

        # Convert to ApiKeyResponse and attach raw_key
        return ApiKeyResponse(**response_data.model_dump(), raw_key=full_raw_key)

    async def validate_api_key(self, raw_key: str) -> Optional[ApiKeyInDb]:
        """Validate an incoming API key.

        Args:
            raw_key: The full raw API key string from the request header

        Returns:
            The API key details if valid, None otherwise

        """
        hashed_key = self._hash_key(raw_key)
        api_key_model = await self.repository.get_valid_by_hashed_key(hashed_key)

        if not api_key_model:
            return None

        return self.orm_to_schema(api_key_model)

    async def list_api_keys(self, organization_id: UUID) -> List[ApiKeyInDb]:
        """List all active API keys for an organization.

        Args:
            organization_id: The ID of the organization

        Returns:
            List of API key details

        """
        keys = await self.repository.list_valid_by_organization(organization_id)
        return self.orm_to_schema_list(keys)

    async def delete_api_key(self, api_key_id: UUID, organization_id: UUID) -> None:
        """Revoke (soft-delete) an API key.

        Args:
            api_key_id: The ID of the key to revoke
            organization_id: The ID of the organization owning the key

        """
        # Ensure the key exists and belongs to the org
        api_key = await self.repository.get_by_id_and_organization(
            api_key_id,
            organization_id,
        )
        if not api_key:
            raise EntityNotFound("API key not found")

        await self.repository.delete_(api_key)
