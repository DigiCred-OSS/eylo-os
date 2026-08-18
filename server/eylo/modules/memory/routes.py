"""Private organization Memory inspection routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from eylo.common.contracts.memory import MemoryLevel
from eylo.common.contracts.memory_reconciliation import MemoryIntegrityState
from eylo.common.database import get_transaction, start_transaction
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.memory.operator_service import (
    MemoryNotFound,
    MemoryOperatorService,
)
from eylo.modules.memory.schemas import (
    MemoryDetailRead,
    MemoryListRead,
    MemorySort,
    MemoryStatus,
    SortDirection,
)

router = APIRouter(prefix="/{organization_id}/memories", tags=[APP_TAG])


@router.get("", response_model=MemoryListRead)
async def list_memories(
    organization_id: UUID,
    level: Annotated[list[MemoryLevel] | None, Query()] = None,
    status: Annotated[list[MemoryStatus] | None, Query()] = None,
    integrity: Annotated[list[MemoryIntegrityState] | None, Query()] = None,
    recalled: bool | None = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    sort: MemorySort = MemorySort.UPDATED_AT,
    direction: SortDirection = SortDirection.DESC,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> MemoryListRead:
    """List saved, recalled, and expired facts for one organization."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        return await MemoryOperatorService(get_transaction()).list(
            organization_id=organization_id,
            levels=level or [],
            statuses=status or [],
            integrities=integrity or [],
            recalled=recalled,
            query=query,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )


@router.get("/{memory_id}", response_model=MemoryDetailRead)
async def get_memory(
    organization_id: UUID,
    memory_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> MemoryDetailRead:
    """Return one exact organization-owned fact and its lifecycle history."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        try:
            return await MemoryOperatorService(get_transaction()).get(
                organization_id=organization_id,
                memory_id=memory_id,
            )
        except MemoryNotFound:
            raise HTTPException(status_code=404, detail="Memory not found.") from None


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


__all__ = ["router"]
