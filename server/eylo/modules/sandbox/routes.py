"""Operator routes for long-running objectives and the workspaces they use.

Two resources, and the second exists mostly so an operator can see and stop
what is running. A feature that executes code needs a kill switch that does not
require shell access to the host.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status

from eylo.common.contracts.sandbox import SandboxError
from eylo.modules.agent_runs.domain import (
    AgentRunLifecycle,
    AgentRunOriginKind,
    ExecutionBudgetNotConfigured,
    ExecutionBudgetUnavailable,
)
from eylo.modules.agent_runs.schemas import AgentRunRead
from eylo.modules.agent_runs.service import (
    AgentRunConflict,
    AgentRunNotFound,
    cancel_agent_run,
    get_agent_run,
    list_objective_agent_runs,
)
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.sandbox.schemas import (
    ObjectiveCreate,
    SandboxGrantCreate,
    SandboxGrantRead,
    SandboxSessionRead,
)
from eylo.pipelines.sandbox import sessions

router = APIRouter(prefix="/{organization_id}", tags=[APP_TAG])


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


# ---------------------------------------------------------------------------
# Objectives
# ---------------------------------------------------------------------------


@router.post(
    "/objectives", status_code=status.HTTP_201_CREATED, response_model=AgentRunRead
)
async def create_objective(
    organization_id: UUID,
    request: ObjectiveCreate,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=240,
    ),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentRunRead:
    """Start long-running work; the agent decides whether it needs a sandbox."""
    _authorize(organization_id, current_user)

    try:
        from eylo.pipelines.sandbox.objectives import create_objective_for_agent

        objective = await create_objective_for_agent(
            organization_id=organization_id,
            member_id=current_user.member_id,
            agent_id=request.agent_id,
            goal=request.goal,
            max_steps=request.max_steps,
            deadline=request.deadline,
            idempotency_token=idempotency_key,
        )
    except (AgentRunConflict, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (
        ExecutionBudgetNotConfigured,
        ExecutionBudgetUnavailable,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return objective


@router.get("/objectives", response_model=list[AgentRunRead])
async def list_objectives(
    organization_id: UUID,
    agent_id: UUID | None = None,
    lifecycle: AgentRunLifecycle | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> list[AgentRunRead]:
    """Objectives for this organization, newest first."""
    _authorize(organization_id, current_user)
    return await list_objective_agent_runs(
        organization_id=organization_id,
        agent_id=agent_id,
        lifecycle=lifecycle,
        limit=limit,
    )


@router.get("/objectives/{objective_id}", response_model=AgentRunRead)
async def read_objective(
    organization_id: UUID,
    objective_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentRunRead:
    """One objective, including the trail of what it has done.

    The progress list is the thing to read when an objective misbehaves: it is
    what the agent itself reads on resume, so it is exactly what the agent
    believed had happened.
    """
    _authorize(organization_id, current_user)
    try:
        run = await get_agent_run(
            organization_id=organization_id,
            run_id=objective_id,
        )
    except AgentRunNotFound as error:
        raise HTTPException(status_code=404) from error
    if run.origin_kind is not AgentRunOriginKind.OBJECTIVE:
        raise HTTPException(status_code=404)
    return run


@router.post("/objectives/{objective_id}/cancel", response_model=AgentRunRead)
async def cancel_objective(
    organization_id: UUID,
    objective_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentRunRead:
    """Stop an objective.

    A running objective may still finish the step it is on — cancelling stops
    the work, not the command already executing. Its workspace is reaped on
    expiry, or immediately through the sandbox route below.
    """
    _authorize(organization_id, current_user)

    # Existence is checked first, and separately, so the two failures cannot be
    # confused. Without this, cancelling *another organization's* objective
    # returned "it has already finished" — misleading, and worse, an admission
    # that it exists. Not-yours and not-there now give the same 404, which is
    # what stops this being a way to probe for other people's work.
    try:
        current = await get_agent_run(
            organization_id=organization_id,
            run_id=objective_id,
        )
        if current.origin_kind is not AgentRunOriginKind.OBJECTIVE:
            raise AgentRunNotFound
        cancelled = await cancel_agent_run(
            organization_id=organization_id,
            run_id=objective_id,
            expected_state_revision=current.state_revision,
        )
        return cancelled.run
    except AgentRunNotFound as error:
        raise HTTPException(status_code=404) from error
    except AgentRunConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


# ---------------------------------------------------------------------------
# Grants
#
# Declared before `/sandboxes/{session_id}`, and must stay that way. FastAPI
# matches in declaration order, so a path parameter accepting any single
# segment swallows `/sandboxes/grants` and the endpoint 422s on "grants is not
# a valid UUID". Nothing about the code reads as wrong when this breaks.
# ---------------------------------------------------------------------------


@router.post(
    "/sandboxes/grants",
    status_code=status.HTTP_201_CREATED,
    response_model=SandboxGrantRead,
)
async def grant_sandbox(
    organization_id: UUID,
    request: SandboxGrantCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Let an agent run code.

    Configuring a sandbox for an organization does not grant it to every agent.
    The request explicitly selects both its ready config and no-egress access.
    """
    _authorize(organization_id, current_user)
    try:
        return await sessions.grant(
            organization_id=organization_id,
            agent_id=request.agent_id,
            sandbox_provider_config_id=request.sandbox_provider_config_id,
            access=request.access,
            max_sessions=request.max_sessions,
        )
    except SandboxError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/sandboxes/grants", response_model=list[SandboxGrantRead])
async def list_sandbox_grants(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Which agents in this organization may run code, and with what reach."""
    _authorize(organization_id, current_user)
    return await sessions.list_grants(organization_id=organization_id)


@router.delete("/sandboxes/grants/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_sandbox(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Stop an agent running code.

    An action already executing may finish. Every later acquisition, including
    restoration of a durable workspace checkpoint, requires the current grant.
    Revocation does not cancel the AgentRun; the session route remains the
    immediate kill switch for live compute.
    """
    _authorize(organization_id, current_user)
    try:
        if not await sessions.revoke(
            organization_id=organization_id, agent_id=agent_id
        ):
            raise HTTPException(status_code=404, detail="That agent has no grant.")
    except SandboxError as error:
        raise HTTPException(status_code=404, detail=str(error))


# ---------------------------------------------------------------------------
# Sandboxes
# ---------------------------------------------------------------------------


@router.get("/sandboxes", response_model=list[SandboxSessionRead])
async def list_sandboxes(
    organization_id: UUID,
    include_destroyed: bool = False,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Workspaces this organization is holding.

    What an operator checks when they want to know what is running and what it
    is costing.
    """
    _authorize(organization_id, current_user)
    return await sessions.list_sessions(
        organization_id=organization_id, include_destroyed=include_destroyed
    )


@router.get("/sandboxes/{session_id}", response_model=SandboxSessionRead)
async def read_sandbox(
    organization_id: UUID,
    session_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    try:
        return await sessions.get_session(session_id, organization_id)
    except SandboxError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.delete("/sandboxes/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_sandbox(
    organization_id: UUID,
    session_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Destroy a workspace now. **The kill switch.**

    This matters more than the usual delete endpoint: a sandbox is running
    code, and an operator who sees one misbehaving needs to stop it without
    shell access to the host and without waiting for an expiry they set in
    calmer circumstances.

    Destroys rather than snapshots. An operator reaching for this wants the
    thing gone, not paused with its files intact.
    """
    _authorize(organization_id, current_user)
    try:
        await sessions.destroy_session(session_id, organization_id)
    except SandboxError as error:
        raise HTTPException(status_code=404, detail=str(error))
