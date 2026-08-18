"""Operator routes for knowledgebases and grants.

Grants are a separate resource from knowledgebases, not a field on one, because
they are a separate decision. Defining what knowledge exists and deciding which
agent may change it are different acts, and an operator should be able to do the
first without implicitly doing the second.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.database import get_transaction, start_transaction
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.knowledgebase.schemas import (
    GrantCreate,
    GrantRead,
    KnowledgeEmbeddingSpaceRead,
    KnowledgeReindexJobRead,
    KnowledgeReindexStatusRead,
    KnowledgebaseCreate,
    KnowledgebaseRead,
    KnowledgebaseReindexRequest,
    KnowledgebaseUpdate,
)
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseNotFound,
    KnowledgebaseService,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.embedding.resolver import resolve_embedding_runtime
from eylo.pipelines.knowledgebase.lifecycle import delete_knowledgebase as delete_kb
from eylo.pipelines.knowledgebase.reindex import (
    inspect_knowledgebase_reindex,
    request_knowledgebase_reindex,
)

router = APIRouter(prefix="/{organization_id}/knowledgebases", tags=[APP_TAG])


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


@router.get("", response_model=list[KnowledgebaseRead])
async def list_knowledgebases(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        service = KnowledgebaseService(get_transaction())
        return await service.list_for_organization(organization_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgebaseRead)
async def create_knowledgebase(
    organization_id: UUID,
    request: KnowledgebaseCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Define a knowledgebase. No vendor is assumed; the caller names one."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        try:
            embedding_space = None
            if request.embedding_provider_config_id is not None:
                runtime = await resolve_embedding_runtime(
                    organization_id,
                    provider_config_id=request.embedding_provider_config_id,
                    db=get_transaction(),
                )
                embedding_space = runtime.space
            service = KnowledgebaseService(get_transaction())
            return await service.create(
                organization_id=organization_id,
                name=request.name,
                vendor=request.vendor,
                scope=request.scope,
                scope_id=request.scope_id,
                writable=request.writable,
                metadata=request.metadata,
                embedding_space=embedding_space,
            )
        except KnowledgebaseNotFound as error:
            raise HTTPException(status_code=404, detail=str(error))
        except KnowledgebaseError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except (InvalidEmbeddingConfig, NotConfiguredError):
            raise HTTPException(
                status_code=400,
                detail="Select a ready organization embedding config.",
            ) from None


@router.get("/{knowledgebase_id}", response_model=KnowledgebaseRead)
async def get_knowledgebase(
    organization_id: UUID,
    knowledgebase_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Return one organization-owned knowledgebase without disclosing others."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        try:
            return await KnowledgebaseService(get_transaction()).get(
                knowledgebase_id,
                organization_id,
            )
        except KnowledgebaseNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{knowledgebase_id}", response_model=KnowledgebaseRead)
async def update_knowledgebase(
    organization_id: UUID,
    knowledgebase_id: UUID,
    request: KnowledgebaseUpdate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = KnowledgebaseService(get_transaction())
        try:
            return await service.update(
                knowledgebase_id,
                organization_id,
                name=request.name,
                writable=request.writable,
                metadata=request.metadata,
            )
        except KnowledgebaseNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except KnowledgebaseError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/{knowledgebase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledgebase(
    organization_id: UUID,
    knowledgebase_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    try:
        await delete_kb(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
        )
    except KnowledgebaseError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/{knowledgebase_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=KnowledgeReindexJobRead,
)
async def reindex_knowledgebase(
    organization_id: UUID,
    knowledgebase_id: UUID,
    request: KnowledgebaseReindexRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    try:
        return await request_knowledgebase_reindex(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            embedding_provider_config_id=request.embedding_provider_config_id,
        )
    except KnowledgebaseNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except KnowledgebaseError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (InvalidEmbeddingConfig, NotConfiguredError):
        raise HTTPException(
            status_code=400,
            detail="Select a ready organization embedding config.",
        ) from None


@router.get(
    "/{knowledgebase_id}/reindex",
    response_model=KnowledgeReindexStatusRead,
)
async def get_knowledgebase_reindex_status(
    organization_id: UUID,
    knowledgebase_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    try:
        inspection = await inspect_knowledgebase_reindex(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
        )
    except KnowledgebaseNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except KnowledgebaseError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    available = inspection.available_space
    target = inspection.target_space
    return KnowledgeReindexStatusRead(
        state=inspection.knowledgebase.reindex_state,
        active_space=_embedding_space_read(inspection.active_space),
        target_space=_embedding_space_read(target),
        available_space=_embedding_space_read(available),
        update_available=(
            (
                target is not None
                and not inspection.active_space.is_compatible_with(target)
            )
            or (
                available is not None
                and not inspection.active_space.is_compatible_with(available)
            )
        ),
        last_error=inspection.knowledgebase.reindex_last_error,
        latest_job=inspection.latest_job,
    )


def _embedding_space_read(space) -> KnowledgeEmbeddingSpaceRead | None:
    if space is None:
        return None
    return KnowledgeEmbeddingSpaceRead(
        provider_config_id=space.provider_config_id,
        provider_config_revision=space.provider_config_revision,
        provider=space.provider,
        model=space.model,
        dimensions=space.dimensions,
        space_id=space.id,
    )


@router.post("/grants", status_code=status.HTTP_201_CREATED, response_model=GrantRead)
async def grant_knowledgebase(
    organization_id: UUID,
    request: GrantCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Give an agent access. Omitting `access` grants READ, never write."""
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = KnowledgebaseService(get_transaction())
        try:
            return await service.grant(
                organization_id=organization_id,
                agent_id=request.agent_id,
                knowledgebase_id=request.knowledgebase_id,
                access=request.access,
            )
        except KnowledgebaseNotFound as error:
            raise HTTPException(status_code=404, detail=str(error))
        except KnowledgebaseError as error:
            raise HTTPException(status_code=400, detail=str(error))


@router.get("/grants/{agent_id}", response_model=list[GrantRead])
async def list_grants(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """What this agent may read and write. The whole of its knowledge surface."""
    _authorize(organization_id, current_user)
    async with start_transaction(ro=True):
        service = KnowledgebaseService(get_transaction())
        try:
            return await service.grants_for_agent(agent_id, organization_id)
        except KnowledgebaseNotFound as error:
            raise HTTPException(status_code=404, detail=str(error))


@router.delete(
    "/grants/{agent_id}/{knowledgebase_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_knowledgebase(
    organization_id: UUID,
    agent_id: UUID,
    knowledgebase_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    async with start_transaction():
        service = KnowledgebaseService(get_transaction())
        try:
            await service.revoke(
                organization_id=organization_id,
                agent_id=agent_id,
                knowledgebase_id=knowledgebase_id,
            )
        except KnowledgebaseError as error:
            raise HTTPException(status_code=404, detail=str(error))
