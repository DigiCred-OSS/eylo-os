"""User management service for platform users."""

from typing import Optional
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.services import EyloBaseService
from eylo.modules.members.exceptions import MemberNotFound
from eylo.modules.members.listing import (
    MemberListQuery,
    MemberSortDirection,
    MemberSortField,
)
from eylo.modules.members.repositories import MemberRepository
from eylo.modules.members.schemas.indb import MemberCreateSchema, MemberInDb
from eylo.modules.organizations.services import OrganizationService


class MemberService(EyloBaseService[MemberInDb]):
    """Service for managing platform users.

    This service is responsible for:
    - Creating users
    - Retrieving users
    - Updating users
    - Managing user sessions
    """

    @property
    def schema(self) -> type[MemberInDb]:
        return MemberInDb

    @property
    def repository(self) -> MemberRepository:
        return self._repository

    @repository.setter
    def repository(self, value: MemberRepository):
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = MemberRepository(db)

    async def get_by_email(self, email: EmailStr) -> MemberInDb:
        member = await self.repository.get_by_email(email)
        if not member:
            raise MemberNotFound(f"{email=} not found")
        return self.orm_to_schema(member)

    async def get_active_by_email(self, email: EmailStr) -> MemberInDb:
        member = await self.repository.get_active_by_email(email)
        if not member:
            raise MemberNotFound(f"{email=} not found")
        return self.orm_to_schema(member)

    async def get_active_by_id(self, member_id: UUID) -> MemberInDb:
        member = await self.repository.get_active_by_id(member_id)
        if not member:
            raise MemberNotFound(f"{member_id=} not found")
        return self.orm_to_schema(member)

    async def get_by_id_and_organization(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> MemberInDb:
        """Resolve a member only through its tenant-bearing identity."""
        member = await self.repository.filter_one_(
            filters=[
                self.repository.model.id == member_id,
                self.repository.model.organization_id == organization_id,
                self.repository.model.deleted.is_(False),
            ]
        )
        if member is None:
            raise MemberNotFound(f"{member_id=} not found")
        return self.orm_to_schema(member)

    async def verify_password(self, entity: MemberInDb, plain_password: str) -> bool:
        from eylo.modules.auth.services.auth_service import AuthService

        return AuthService.verify_password(plain_password, entity.password)

    async def create_(
        self, organization_id: UUID, request: MemberCreateSchema
    ) -> MemberInDb:
        entity = await self.repository.create(
            organization_id=organization_id,
            email=request.email,
            password=request.password,
        )
        return self.orm_to_schema(entity)

    async def get_by_id_email_organization(
        self, member_id: UUID, email: EmailStr, organization_id: UUID
    ) -> MemberInDb:
        member = await self.repository.filter_one_(
            filters=[
                self.repository.model.id == member_id,
                self.repository.model.email == email,
                self.repository.model.organization_id == organization_id,
            ]
        )
        if not member:
            raise MemberNotFound(f"{member_id=} not found")
        s_organization = await OrganizationService(
            self.repository.db_session
        ).get_(organization_id)
        s_member = self.orm_to_schema(member)
        s_member.organization = s_organization
        return s_member

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        query: MemberListQuery | None = None,
    ) -> list[MemberInDb]:
        """List owned members with server-side search, filtering, and sorting."""
        query = query or MemberListQuery()
        model = self.repository.model
        sort_column = {
            MemberSortField.NAME: model.name,
            MemberSortField.EMAIL: model.email,
            MemberSortField.STATUS: model.status,
            MemberSortField.LAST_LOGIN: model.last_login,
            MemberSortField.CREATED_AT: model.created_at,
        }[query.sort_by]
        order = (
            sort_column.asc().nulls_last()
            if query.sort_direction is MemberSortDirection.ASC
            else sort_column.desc().nulls_last()
        )
        return self.orm_to_schema_list(
            await self.repository.filter_(
                filters=self._collection_filters(organization_id, query),
                limit=limit,
                offset=offset,
                order_by=[order, model.id.desc()],
            )
        )

    async def count_by_organization(
        self,
        organization_id: UUID,
        query: MemberListQuery | None = None,
    ) -> int:
        """Count the same filtered collection returned by the list query."""
        query = query or MemberListQuery()
        return await self.repository.count_(
            filters=self._collection_filters(organization_id, query)
        )

    def _collection_filters(
        self,
        organization_id: UUID,
        query: MemberListQuery,
    ) -> list:
        """Build the one filter set shared by collection rows and totals."""
        model = self.repository.model
        filters = [
            model.organization_id == organization_id,
            model.deleted.is_(False),
        ]
        if query.search:
            term = f"%{query.search}%"
            filters.append(or_(model.name.ilike(term), model.email.ilike(term)))
        if query.statuses:
            filters.append(model.status.in_(query.statuses))
        return filters

    async def list_by_ids(
        self,
        member_ids: list[UUID],
        organization_id: UUID,
    ) -> list[MemberInDb]:
        """Bulk fetch members by IDs within an organization.

        Args:
            member_ids: List of member IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of member schema objects matching the provided IDs

        """
        members = await self.repository.list_by_ids(
            member_ids=member_ids,
            organization_id=organization_id,
        )
        return self.orm_to_schema_list(members)
