"""Member-private status route for asynchronous Eylo deletion."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.deletions.domain import DeletionJobNotFound
from eylo.modules.deletions.schemas import DeletionJobApiResponse
from eylo.modules.deletions.service import DeletionJobService

router = APIRouter(prefix="/deletions", tags=["deletions"])


@router.get("/{job_id}", response_model=DeletionJobApiResponse)
async def get_deletion_job(
    job_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> DeletionJobApiResponse:
    """Return one owned content-free deletion monitor or the same 404."""
    try:
        async with start_transaction(ro=True) as session:
            row = await DeletionJobService(session).get(
                organization_id=current_user.organization_id,
                job_id=job_id,
            )
            return DeletionJobApiResponse.from_record(row)
    except DeletionJobNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deletion not found",
        ) from None


__all__ = ["router"]
