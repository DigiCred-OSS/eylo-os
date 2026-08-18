"""Authenticated member authority at the HTTP organization boundary."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user


async def require_member_path_organization(
    request: Request,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> CurrentUserSchema:
    """Hide every organization-scoped member route from other tenants.

    Routes without an ``organization_id`` path parameter remain authenticated
    and infer scope from ``current_user``. Routes with that parameter are
    rejected here, before module-specific validation or lookup can disclose
    whether a referenced resource exists.
    """
    organization_id = request.path_params.get("organization_id")
    if organization_id is not None and str(current_user.organization_id) != str(
        organization_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return current_user
