"""Transport orchestration for the `members` domain."""

from uuid import UUID

from fastapi import HTTPException

from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.members.exceptions import MemberNotFound
from eylo.modules.members.listing import MemberListQuery
from eylo.modules.members.schemas.api import (
    MemberApiResponseSchema,
    MemberFilterSchema,
    MembersPaginated,
)
from eylo.modules.members.services import MemberService


class MemberController:
    """MemberController behavior for the "members" domain."""

    def __init__(self):
        """Initialize Member Controller."""
        self.member_service = MemberService()

    async def get(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> MemberApiResponseSchema:
        """Get Member by ID."""
        try:
            member = await self.member_service.get_by_id_and_organization(
                member_id,
                organization_id,
            )
            return MemberApiResponseSchema.model_validate(member.model_dump())
        except MemberNotFound:
            raise HTTPException(
                status_code=404,
                detail=f"Member with ID {member_id} not found.",
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Member could not be retrieved.",
            ) from None

    async def list_members(
        self,
        organization_id: UUID,
        pagination: PaginationParams,
        current_user: CurrentUserSchema,
        filters: MemberFilterSchema | None = None,
        query: MemberListQuery | None = None,
    ) -> MembersPaginated:
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=404)
        async with start_transaction(ro=True):
            # If specific member IDs requested, fetch only those
            if filters and filters.member_ids:
                members = await self.member_service.list_by_ids(
                    member_ids=filters.member_ids,
                    organization_id=current_user.organization_id,
                )
                return MembersPaginated(
                    data=[
                        MemberApiResponseSchema.model_validate(member.model_dump())
                        for member in members
                    ],
                    total=len(members),
                    limit=len(members),
                    page=1,
                )

            # Otherwise, paginated list
            members = await self.member_service.list_by_organization(
                organization_id=current_user.organization_id,
                limit=pagination.limit,
                offset=pagination.get_offset(),
                query=query,
            )
            total = await self.member_service.count_by_organization(
                current_user.organization_id,
                query,
            )
            return MembersPaginated(
                data=[
                    MemberApiResponseSchema.model_validate(member.model_dump())
                    for member in members
                ],
                total=total,
                limit=pagination.limit,
                page=pagination.page,
                has_more=pagination.get_offset() + len(members) < total,
            )
