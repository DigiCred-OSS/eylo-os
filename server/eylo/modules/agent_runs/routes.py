"""Private organization-scoped routes for durable agent runs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eylo.modules.agent_runs.budgets import (
    get_organization_execution_budget,
    put_organization_execution_budget,
)
from eylo.modules.agent_runs.domain import (
    ExecutionBudgetConflict,
    ExecutionBudgetNotConfigured,
    ExecutionBudgetUnavailable,
)
from eylo.modules.agent_runs.schemas import (
    AgentInputRequestRead,
    AgentInputResponseRequest,
    AgentRunCancelRequest,
    AgentRunCancellationRead,
    AgentRunRead,
    OrganizationExecutionBudgetRead,
    OrganizationExecutionBudgetUpsert,
)
from eylo.modules.agent_runs.service import (
    AgentInputRequestNotFound,
    AgentRunConflict,
    AgentRunNotFound,
    answer_input_request,
    cancel_agent_run,
    get_agent_run,
    list_agent_runs,
)
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user

router = APIRouter(prefix="/{organization_id}/agent-runs", tags=[APP_TAG])


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


@router.get("/budget", response_model=OrganizationExecutionBudgetRead)
async def get_budget(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> OrganizationExecutionBudgetRead:
    _authorize(organization_id, current_user)
    try:
        return await get_organization_execution_budget(
            organization_id=organization_id,
        )
    except ExecutionBudgetNotConfigured as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/budget", response_model=OrganizationExecutionBudgetRead)
async def put_budget(
    organization_id: UUID,
    request: OrganizationExecutionBudgetUpsert,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> OrganizationExecutionBudgetRead:
    _authorize(organization_id, current_user)
    try:
        return await put_organization_execution_budget(
            organization_id=organization_id,
            command=request,
        )
    except (
        ExecutionBudgetConflict,
        ExecutionBudgetUnavailable,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("", response_model=list[AgentRunRead])
async def list_all(
    organization_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> list[AgentRunRead]:
    _authorize(organization_id, current_user)
    return await list_agent_runs(
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{run_id}/cancel",
    response_model=AgentRunCancellationRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel(
    organization_id: UUID,
    run_id: UUID,
    request: AgentRunCancelRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentRunCancellationRead:
    _authorize(organization_id, current_user)
    try:
        return await cancel_agent_run(
            organization_id=organization_id,
            run_id=run_id,
            expected_state_revision=request.expected_state_revision,
        )
    except AgentRunNotFound as error:
        raise HTTPException(status_code=404) from error
    except AgentRunConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/{run_id}/input-requests/{request_id}/response",
    response_model=AgentInputRequestRead,
)
async def answer(
    organization_id: UUID,
    run_id: UUID,
    request_id: UUID,
    request: AgentInputResponseRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentInputRequestRead:
    _authorize(organization_id, current_user)
    try:
        return await answer_input_request(
            organization_id=organization_id,
            run_id=run_id,
            request_id=request_id,
            member_id=current_user.member_id,
            command=request,
        )
    except (AgentRunNotFound, AgentInputRequestNotFound) as error:
        raise HTTPException(status_code=404) from error
    except AgentRunConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{run_id}", response_model=AgentRunRead)
async def read_one(
    organization_id: UUID,
    run_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentRunRead:
    _authorize(organization_id, current_user)
    try:
        return await get_agent_run(
            organization_id=organization_id,
            run_id=run_id,
        )
    except AgentRunNotFound as error:
        raise HTTPException(status_code=404) from error
