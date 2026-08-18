"""Repository for platform user database operations."""

from typing import List, Optional
from uuid import UUID

from pydantic import EmailStr

from eylo.common.repositories import BaseORMRepository
from eylo.modules.members.models import MemberModel, MemberStatus


class MemberRepository(BaseORMRepository[MemberModel]):
    def __init__(self, session):
        super().__init__(session)

    @property
    def model(self) -> type[MemberModel]:
        return MemberModel

    @staticmethod
    def _clean_email(email: str | EmailStr) -> str:
        return email.lower()

    async def get_by_email(self, email: EmailStr) -> Optional[MemberModel]:
        email = self._clean_email(email)
        filters = [self.model.email == email]
        return await self.filter_one_(filters=filters)

    async def get_active_by_email(self, email: EmailStr) -> Optional[MemberModel]:
        return await self.filter_one_(
            filters=[
                self.model.email == self._clean_email(email),
                self.model.deleted.is_(False),
                self.model.status == MemberStatus.ACTIVE,
            ]
        )

    async def get_active_by_id(self, member_id: UUID) -> Optional[MemberModel]:
        return await self.filter_one_(
            filters=[
                self.model.id == member_id,
                self.model.deleted.is_(False),
                self.model.status == MemberStatus.ACTIVE,
            ]
        )

    async def list_by_organization(
        self, organization_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[MemberModel]:
        filters = [
            self.model.organization_id == organization_id,
        ]
        return await self.filter_(
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=[self.model.created_at],
        )

    async def create(
        self, organization_id: UUID, email: str, password: str
    ) -> MemberModel:
        email = self._clean_email(email)
        member = self.model(
            organization_id=organization_id, email=email, password=password, name=email
        )
        return await self.save_(member)

    async def list_by_ids(
        self,
        member_ids: list[UUID],
        organization_id: UUID,
    ) -> list[MemberModel]:
        """Bulk fetch members by IDs within an organization.

        Args:
            member_ids: List of member IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of member models matching the IDs

        """
        if not member_ids:
            return []

        filters = [
            self.model.id.in_(member_ids),
            self.model.organization_id == organization_id,
        ]
        return await self.filter_all_(filters=filters)
