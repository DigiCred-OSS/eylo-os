"""FastAPI pagination dependency."""

from typing import Annotated

from fastapi import Query

from eylo.common.schemas import PaginationParams


def get_pagination(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
) -> PaginationParams:
    """Get Pagination Parameters."""
    return PaginationParams(page=page, limit=limit, total=0)
