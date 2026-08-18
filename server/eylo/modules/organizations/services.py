"""Application services for the `organizations` domain."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.services import EyloBaseService
from eylo.modules.organizations.repositories import OrganizationRepository

from .schemas import OrganisationCreateSchema, OrganizationModelSchema

logger = logging.getLogger(__name__)


class OrganizationService(EyloBaseService[OrganizationModelSchema]):
    """OrganizationService behavior for the "organizations" domain."""

    @property
    def schema(self) -> OrganizationModelSchema:
        """Schema for the "organizations" domain."""
        return OrganizationModelSchema

    @property
    def repository(self) -> OrganizationRepository:
        """Repository for the "organizations" domain."""
        return self._repository

    @repository.setter
    def repository(self, value: OrganizationRepository):
        """Repository for the "organizations" domain."""
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        """Init for the "organizations" domain."""
        self._repository = OrganizationRepository(db)
        self._db = db

    async def create(
        self, org_data: OrganisationCreateSchema
    ) -> OrganizationModelSchema:
        """Create for the "organizations" domain."""
        entity = await self.repository.create(name=org_data.name)
        await self._seed_background_agents(entity.id)
        return self.orm_to_schema(entity)

    async def _seed_background_agents(self, organization_id: UUID) -> None:
        """Create the first-party background agents, unattached."""
        from eylo.modules.agents.services.background_seeds import (
            seed_background_agents,
        )

        db = self.repository.db_session
        try:
            async with db.begin_nested():
                await seed_background_agents(organization_id, db)
        except Exception as error:
            logger.error(
                "Could not seed background agents for organization=%s "
                "error_type=%s. "
                "The organization is usable; seeding is idempotent and can be "
                "retried.",
                organization_id,
                type(error).__name__,
            )

    async def get_(self, pk: UUID) -> OrganizationModelSchema:
        """Get for the "organizations" domain."""
        entity = await self.repository.get_(pk)
        return self.orm_to_schema(entity)
