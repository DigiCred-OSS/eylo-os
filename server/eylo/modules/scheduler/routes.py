"""Operator routes for schedules.

Creation validates the recurrence *and* the action before storing either. Both
produce errors an operator can only act on while they are still looking at the
thing they typed — a schedule stored with a rule that does not parse, or an
action nothing handles, is one that fails at a time nobody is watching.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from eylo.common.contracts.scheduler import InvalidRecurrence, Recurrence
from eylo.common.revisions import DefinitionRevisionError, RevisionConflictError
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.scheduler.actions import registered_actions
from eylo.modules.scheduler.discovery import register_scheduled_actions
from eylo.modules.scheduler.domain import ScheduleConflictError
from eylo.modules.scheduler.schemas import (
    ScheduleCreate,
    ScheduleRead,
    ScheduleRevisionRevoke,
    ScheduleRunRead,
    ScheduleUpdate,
)
from eylo.modules.scheduler.service import (
    ScheduleNotFound,
    cancel_schedule,
    create_schedule,
    get_schedule,
    list_runs,
    list_schedules,
    revoke_schedule_revision,
    update_schedule,
)

router = APIRouter(prefix="/{organization_id}/schedules", tags=[APP_TAG])


def _authorize(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)


# ---------------------------------------------------------------------------
# `/actions` is declared before `/{schedule_id}`, and must stay that way.
# FastAPI matches in declaration order, so a path parameter accepting any
# single segment swallows it and the endpoint 422s on "actions is not a valid
# UUID". Nothing about the code reads as wrong when this breaks.
# ---------------------------------------------------------------------------


@router.get("/actions")
async def list_actions(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Every action a schedule can name.

    Exposed because the alternative is an operator guessing, and a guess
    becomes a schedule that fails its first run.
    """
    _authorize(organization_id, current_user)
    register_scheduled_actions()
    return {"actions": list(registered_actions())}


@router.get("", response_model=list[ScheduleRead])
async def list_all(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    return await list_schedules(organization_id=organization_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduleRead)
async def create(
    organization_id: UUID,
    request: ScheduleCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Define a schedule. Refuses anything that could not run."""
    _authorize(organization_id, current_user)
    try:
        schedule_id, _ = await create_schedule(
            organization_id=organization_id,
            key=request.key,
            name=request.name,
            action=request.action,
            payload=request.payload,
            recurrence=Recurrence(
                rule=request.rule,
                timezone=request.timezone,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
            ),
            misfire_policy=request.misfire_policy,
            agent_id=request.agent_id,
            published_by=current_user.member_id,
        )
    except InvalidRecurrence as error:
        raise HTTPException(status_code=400, detail=str(error))
    except ScheduleConflictError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except DefinitionRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return await get_schedule(UUID(schedule_id), organization_id=organization_id)


@router.put("/{schedule_id}", response_model=ScheduleRead)
async def update(
    organization_id: UUID,
    schedule_id: UUID,
    request: ScheduleUpdate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Append one explicit immutable definition revision."""
    _authorize(organization_id, current_user)
    try:
        await update_schedule(
            schedule_id,
            organization_id=organization_id,
            expected_revision=request.expected_revision,
            name=request.name,
            action=request.action,
            payload=request.payload,
            recurrence=Recurrence(
                rule=request.rule,
                timezone=request.timezone,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
            ),
            misfire_policy=request.misfire_policy,
            agent_id=request.agent_id,
            published_by=current_user.member_id,
        )
    except InvalidRecurrence as error:
        raise HTTPException(status_code=400, detail=str(error))
    except ScheduleNotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except DefinitionRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return await get_schedule(schedule_id, organization_id=organization_id)


@router.get("/{schedule_id}", response_model=ScheduleRead)
async def read_one(
    organization_id: UUID,
    schedule_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    _authorize(organization_id, current_user)
    try:
        return await get_schedule(schedule_id, organization_id=organization_id)
    except ScheduleNotFound as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/{schedule_id}/runs", response_model=list[ScheduleRunRead])
async def read_runs(
    organization_id: UUID,
    schedule_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """What this schedule has actually done, newest first."""
    _authorize(organization_id, current_user)
    try:
        await get_schedule(schedule_id, organization_id=organization_id)
    except ScheduleNotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
    return await list_runs(schedule_id, organization_id=organization_id)


@router.post("/{schedule_id}/revisions/{revision}/revoke", status_code=204)
async def revoke_revision(
    organization_id: UUID,
    schedule_id: UUID,
    revision: int,
    request: ScheduleRevisionRevoke,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> None:
    """Emergency-stop an exact schedule revision with durable reason."""
    _authorize(organization_id, current_user)
    try:
        await revoke_schedule_revision(
            schedule_id,
            revision,
            organization_id=organization_id,
            actor_id=current_user.member_id,
            reason=request.reason,
        )
    except ScheduleNotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
    except DefinitionRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel(
    organization_id: UUID,
    schedule_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Retire a schedule. Runs it already produced keep their history."""
    _authorize(organization_id, current_user)
    try:
        await cancel_schedule(schedule_id, organization_id=organization_id)
    except ScheduleNotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
