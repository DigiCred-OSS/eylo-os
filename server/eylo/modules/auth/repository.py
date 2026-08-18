"""Persistence access for the `auth` domain."""

from typing import Optional, Type
from uuid import UUID

from sqlalchemy import func, or_

from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.modules.auth.models import ApiKeyModel, AuthSessionModel
from eylo.modules.auth.schemas import ApiKeyCreate, AuthSessionCreate


class AuthSessionRepository(BaseORMRepository[AuthSessionModel]):
    """Repository for authentication session data operations."""

    @property
    def model(self) -> Type[AuthSessionModel]:
        """Returns the AuthSessionModel class."""
        return AuthSessionModel

    async def create_(self, data: AuthSessionCreate) -> AuthSessionModel:
        """Creates a new session in the database from validated schema data."""
        session = map_schema_to_model(self.model, data)
        return await self.save_(session)

    async def get_by_token(self, token: str) -> Optional[AuthSessionModel]:
        """Retrieve a session by its unique session token."""
        filters = [
            self.model.session_token == token,
            self.model.deleted.is_(False),
        ]
        return await self.filter_one_(filters=filters)


class ApiKeyRepository(BaseORMRepository[ApiKeyModel]):
    """Repository for API Key data operations."""

    @property
    def model(self) -> Type[ApiKeyModel]:
        """Returns the ApiKeyModel class."""
        return ApiKeyModel

    async def create_(
        self,
        data: ApiKeyCreate,
        organization_id: UUID,
        key_prefix: str,
        hashed_key: str,
    ) -> ApiKeyModel:
        """Creates a new API Key in the database."""
        api_key = map_schema_to_model(self.model, data)
        setattr(api_key, "organization_id", organization_id)
        setattr(api_key, "key_prefix", key_prefix)
        setattr(api_key, "hashed_key", hashed_key)
        return await self.save_(api_key)

    async def get_valid_by_hashed_key(self, hashed_key: str) -> Optional[ApiKeyModel]:
        """Return a currently valid API key by its hash."""
        filters = [
            self.model.hashed_key == hashed_key,
            self.model.is_active.is_(True),
            self.model.deleted.is_(False),
            or_(
                self.model.expires_at.is_(None),
                self.model.expires_at > func.now(),
            ),
        ]
        return await self.filter_one_(filters=filters)

    async def list_valid_by_organization(self, organization_id: UUID) -> list[ApiKeyModel]:
        filters = [
            self.model.organization_id == organization_id,
            self.model.is_active.is_(True),
            self.model.deleted.is_(False),
            or_(
                self.model.expires_at.is_(None),
                self.model.expires_at > func.now(),
            ),
        ]
        return await self.filter_all_(filters=filters)

    async def get_by_id_and_organization(
        self, api_key_id: UUID, organization_id: UUID
    ) -> Optional[ApiKeyModel]:
        return await self.filter_one_(
            filters=[
                self.model.id == api_key_id,
                self.model.organization_id == organization_id,
                self.model.deleted.is_(False),
            ]
        )
