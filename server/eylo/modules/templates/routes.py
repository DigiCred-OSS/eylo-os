"""Authenticated HTTP lifecycle for organization-owned templates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, NoReturn, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.database import start_transaction
from eylo.common.revisions import (
    DefinitionNotPublishedError,
    DefinitionRevisionError,
    DefinitionRevokedError,
    DefinitionWithdrawnError,
    InvalidDefinitionRevisionError,
    RevisionConflictError,
)
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.templates.domain import (
    InvalidTemplateError,
    TemplateConflictError,
    TemplateError,
    TemplateNotFoundError,
)
from eylo.modules.templates.schemas import (
    TemplateCreateRequest,
    TemplateDraftUpdateRequest,
    TemplatePreviewRequest,
    TemplatePublishRequest,
    TemplateRenderRequest,
    TemplateRenderResponse,
    TemplateResponse,
    TemplateRevisionResponse,
    TemplateRevokeRequest,
)
from eylo.modules.templates.service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])

Result = TypeVar("Result")


async def _run(
    operation: Callable[[TemplateService], Awaitable[Result]],
    *,
    read_only: bool = False,
) -> Result:
    error: TemplateError | DefinitionRevisionError | None = None
    async with start_transaction(ro=read_only) as db:
        try:
            return await operation(TemplateService(db))
        except (TemplateError, DefinitionRevisionError) as caught:
            await db.rollback()
            error = caught
    if error is None:
        raise RuntimeError("Template operation completed without a result.")
    _raise_http(error)


def _raise_http(error: TemplateError | DefinitionRevisionError) -> NoReturn:
    if isinstance(error, TemplateNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found.",
        ) from None
    if isinstance(error, InvalidTemplateError | InvalidDefinitionRevisionError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(
        error,
        TemplateConflictError
        | RevisionConflictError
        | DefinitionNotPublishedError
        | DefinitionWithdrawnError
        | DefinitionRevokedError,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(error),
    ) from error


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreateRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateResponse:
    async def create(service: TemplateService):
        return await service.create(
            organization_id=current_user.organization_id,
            name=request.name,
            kind=request.kind,
            body=request.body,
            variable_schema=request.variable_schema.to_storage(),
        )

    return TemplateResponse.model_validate(await _run(create))


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> list[TemplateResponse]:
    rows = await _run(
        lambda service: service.list(
            organization_id=current_user.organization_id,
        ),
        read_only=True,
    )
    return [TemplateResponse.model_validate(row) for row in rows]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateResponse:
    row = await _run(
        lambda service: service.get(
            organization_id=current_user.organization_id,
            template_id=template_id,
        ),
        read_only=True,
    )
    return TemplateResponse.model_validate(row)


@router.patch("/{template_id}/draft", response_model=TemplateResponse)
async def update_template_draft(
    template_id: UUID,
    request: TemplateDraftUpdateRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateResponse:
    row = await _run(
        lambda service: service.update_draft(
            organization_id=current_user.organization_id,
            template_id=template_id,
            expected_draft_version=request.expected_draft_version,
            body=request.body,
            variable_schema=(
                None
                if request.variable_schema is None
                else request.variable_schema.to_storage()
            ),
        )
    )
    return TemplateResponse.model_validate(row)


@router.post("/{template_id}/preview", response_model=TemplateRenderResponse)
async def preview_template(
    template_id: UUID,
    request: TemplatePreviewRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateRenderResponse:
    rendered = await _run(
        lambda service: service.preview(
            organization_id=current_user.organization_id,
            template_id=template_id,
            consumer_kind=request.consumer_kind,
            values=request.variables,
        ),
        read_only=True,
    )
    return TemplateRenderResponse.from_domain(
        rendered,
        template_id=template_id,
        draft_version=rendered.draft_version,
    )


@router.post("/{template_id}/publish", response_model=TemplateRevisionResponse)
async def publish_template(
    template_id: UUID,
    request: TemplatePublishRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateRevisionResponse:
    row = await _run(
        lambda service: service.publish(
            organization_id=current_user.organization_id,
            template_id=template_id,
            expected_draft_version=request.expected_draft_version,
        )
    )
    return TemplateRevisionResponse.model_validate(row)


@router.get(
    "/{template_id}/revisions/{revision}",
    response_model=TemplateRevisionResponse,
)
async def get_template_revision(
    template_id: UUID,
    revision: int,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateRevisionResponse:
    row = await _run(
        lambda service: service.get_revision(
            organization_id=current_user.organization_id,
            template_id=template_id,
            revision=revision,
        ),
        read_only=True,
    )
    return TemplateRevisionResponse.model_validate(row)


@router.post(
    "/{template_id}/revisions/{revision}/render",
    response_model=TemplateRenderResponse,
)
async def render_template_revision(
    template_id: UUID,
    revision: int,
    request: TemplateRenderRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateRenderResponse:
    rendered = await _run(
        lambda service: service.render_exact(
            organization_id=current_user.organization_id,
            template_id=template_id,
            revision=revision,
            consumer_kind=request.consumer_kind,
            values=request.variables,
        ),
        read_only=True,
    )
    return TemplateRenderResponse.from_domain(
        rendered,
        template_id=template_id,
        revision=revision,
    )


@router.post("/{template_id}/withdraw", response_model=TemplateResponse)
async def withdraw_template(
    template_id: UUID,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateResponse:
    row = await _run(
        lambda service: service.withdraw(
            organization_id=current_user.organization_id,
            template_id=template_id,
        )
    )
    return TemplateResponse.model_validate(row)


@router.post(
    "/{template_id}/revisions/{revision}/revoke",
    response_model=TemplateRevisionResponse,
)
async def revoke_template_revision(
    template_id: UUID,
    revision: int,
    request: TemplateRevokeRequest,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> TemplateRevisionResponse:
    row = await _run(
        lambda service: service.revoke(
            organization_id=current_user.organization_id,
            template_id=template_id,
            revision=revision,
            actor_id=current_user.member_id,
            reason=request.reason,
        )
    )
    return TemplateRevisionResponse.model_validate(row)


__all__ = ["router"]
