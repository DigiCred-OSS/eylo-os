"""Repository module for organizations.

This module contains the repository classes for the organizations domain.
"""

from typing import Type

from eylo.common.repositories import BaseORMRepository
from eylo.modules.organizations.models import OrganizationModel


class OrganizationRepository(BaseORMRepository[OrganizationModel]):
    """Repository for organizations.

    This repository handles database operations for organization entities.
    """

    def __init__(self, session):
        super().__init__(session)

    @property
    def model(self) -> Type[OrganizationModel]:
        """Get the model class for this repository.

        Returns
        -------
            Type[Organizations]: The Organizations model class

        """
        return OrganizationModel

    async def create(self, name: str) -> OrganizationModel:
        org = self.model(
            name=name,
        )
        return await self.save_(org)
