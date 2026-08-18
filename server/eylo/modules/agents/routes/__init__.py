"""HTTP routes for the `agents` domain."""

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.common.schemas import PaginationParams
from eylo.common.utils.get_pagination import get_pagination
from eylo.modules.agents.controllers import AgentController, AgentSwarmController
from eylo.modules.agents.domain import (
    InvalidSwarmDefinitionError,
    SwarmMemberNotFoundError,
    SwarmNotFoundError,
)
from eylo.modules.agents.exceptions import (
    AgentError,
    AgentNotFoundError,
    DuplicateAgentError,
)
from eylo.modules.agents.listing import (
    AgentListQuery,
    AgentSortDirection,
    AgentSortField,
)
from eylo.modules.agents.models import AgentKind, AgentStatus
from eylo.modules.agents.schemas.api import (
    AgentCreateRequestSchema,
    AgentEffectiveVoiceStackResponseSchema,
    AgentPublishRequestSchema,
    AgentResponseSchema,
    AgentRevokeRequestSchema,
    AgentSwarmCreateRequestSchema,
    AgentSwarmMappingCreateRequestSchema,
    AgentSwarmMappingDeleteRequestSchema,
    AgentSwarmMappingResponseSchema,
    AgentSwarmPublishRequestSchema,
    AgentSwarmResponseSchema,
    AgentSwarmRevisionResponseSchema,
    AgentSwarmRevokeRequestSchema,
    AgentSwarmUpdateRequestSchema,
    AgentToolRequest,
    AgentToolsResponseSchema,
    AgentUpdateRequestSchema,
    AgentsPaginated,
)
from eylo.modules.agents.schemas.indb import (
    AgentBackgroundAgentCreate,
    AgentBackgroundAgentInDb,
    AgentBackgroundAgentUpdate,
    AgentToolInDb,
)
from eylo.modules.agents.services.background_agents import (
    AgentBackgroundAgentService,
)
from eylo.modules.auth.constants import APP_TAG
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user

router = APIRouter(prefix="/{organization_id}/agents", tags=[APP_TAG])


@asynccontextmanager
async def _swarm_transaction() -> AsyncIterator[None]:
    """Translate one swarm application transaction into stable HTTP outcomes."""
    try:
        async with start_transaction():
            yield
    except (SwarmNotFoundError, SwarmMemberNotFoundError):
        raise HTTPException(status_code=404) from None
    except (
        InvalidSwarmDefinitionError,
        DefinitionRevisionError,
        IntegrityError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

@router.post("", response_model=AgentResponseSchema)
async def create_agent(
    organization_id: UUID,
    request: AgentCreateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Create a new agent for the current user's organization."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        try:
            agent = await AgentController().create_agent(organization_id, request)
            return agent
        except DuplicateAgentError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agent_id}", response_model=AgentResponseSchema)
async def get_agent(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentResponseSchema:
    """Retrieve details of a specific agent."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    return await AgentController().get_agent(agent_id, current_user.organization_id)


@router.get(
    "/{agent_id}/effective-voice-stack",
    response_model=AgentEffectiveVoiceStackResponseSchema,
)
async def get_effective_voice_stack(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AgentEffectiveVoiceStackResponseSchema:
    """Return the exact voice refs copied into the published Agent revision."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    return await AgentController().get_effective_voice_stack(
        organization_id=current_user.organization_id,
        agent_id=agent_id,
    )


@router.put("/{agent_id}", response_model=AgentResponseSchema)
async def update_agent(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentUpdateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Create a new agent for the current user's organization."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        try:
            agent = await AgentController().update_agent(
                organization_id, agent_id, request
            )
            return agent
        except DuplicateAgentError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=AgentsPaginated)
async def list_agents(
    organization_id: UUID,
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    agent_ids: Annotated[list[UUID] | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[
        list[AgentStatus] | None,
        Query(alias="status"),
    ] = None,
    kind: Annotated[list[AgentKind] | None, Query()] = None,
    sort_by: Annotated[AgentSortField, Query()] = AgentSortField.UPDATED_AT,
    sort_direction: Annotated[
        AgentSortDirection,
        Query(),
    ] = AgentSortDirection.DESC,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    return await AgentController().list_agents(
        organization_id,
        pagination,
        current_user,
        AgentListQuery(
            agent_ids=tuple(agent_ids or ()),
            search=search,
            statuses=tuple(status_filter or ()),
            kinds=tuple(kind or ()),
            sort_by=sort_by,
            sort_direction=sort_direction,
        ),
    )


@router.patch("/{agent_id}", response_model=AgentResponseSchema)
async def update_agent_route(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentUpdateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Update an existing agent.

    Args:
        agent_id: The ID of the agent to update.
        request: The request payload with update data.
        current_user: The authenticated user.

    Returns:
        AgentResponseSchema: The updated agent.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        controller = AgentController()
        updated_agent = await controller.update_agent_details(
            agent_id=agent_id,
            organization_id=current_user.organization_id,
            request_payload=request,
        )
        return updated_agent


@router.delete("/{agent_id}", response_model=AgentResponseSchema)
async def deactivate_agent_route(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Deactivate (soft delete) an agent.

    Args:
        agent_id: The ID of the agent to deactivate.
        current_user: The authenticated user.

    Returns:
        AgentResponseSchema: The deactivated agent.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        controller = AgentController()
        deactivated_agent = await controller.deactivate_agent_status(
            agent_id=agent_id, organization_id=current_user.organization_id
        )
        return deactivated_agent


# Tool management routes
@router.post(
    "/{agent_id}/tools",
    response_model=AgentToolInDb,
    status_code=status.HTTP_201_CREATED,
)
async def assign_tool_to_agent(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentToolRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Assign a tool to an agent."""
    return await AgentController().assign_tool_to_agent(
        organization_id, agent_id, request, current_user
    )


@router.get("/{agent_id}/tools", response_model=AgentToolsResponseSchema)
async def list_agent_tools(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List all tools assigned to an agent."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    tools = await AgentController().list_agent_tools(
        agent_id,
        organization_id,
    )
    return {"items": tools}


@router.delete("/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tool_from_agent(
    organization_id: UUID,
    agent_id: UUID,
    tool_id: UUID,
    expected_draft_version: Annotated[int, Query(gt=0)],
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Remove a tool from an agent."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    await AgentController().remove_tool_from_agent(
        agent_id,
        tool_id,
        organization_id,
        expected_draft_version,
    )
    return


@router.put("/{agent_id}/publish", response_model=AgentResponseSchema)
async def publish_agent(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentPublishRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Publish the complete mutable draft as one immutable revision."""
    return await AgentController().publish_agent(
        organization_id=organization_id,
        agent_id=agent_id,
        expected_draft_version=request.expected_draft_version,
        current_user=current_user,
    )


@router.put("/{agent_id}/unpublish", response_model=AgentResponseSchema)
async def withdraw_agent(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Withdraw the stable alias; already pinned work keeps its exact revision."""
    return await AgentController().withdraw_agent(
        organization_id=organization_id,
        agent_id=agent_id,
        current_user=current_user,
    )


@router.post("/{agent_id}/revisions/revoke", response_model=AgentResponseSchema)
async def revoke_agent_revision(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentRevokeRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Emergency-revoke one exact revision and request run cancellation."""
    return await AgentController().revoke_agent_revision(
        organization_id=organization_id,
        agent_id=agent_id,
        revision=request.revision,
        reason=request.reason,
        current_user=current_user,
    )


# Agent Stats

agent_stats_router = APIRouter(prefix="/{organization_id}/agent-stats", tags=[APP_TAG])


@agent_stats_router.get("/count")
async def agent_stats_count(
    organization_id: UUID,
    status: Annotated[list[str] | None, Query()] = None,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> int:
    """Get count of agents, optionally filtered by status.

    Args:
        organization_id (UUID): Organization ID.
        status (list[str] | None): Optional list of agent statuses to filter.
        current_user (CurrentUserSchema): Authenticated user.

    Returns:
        int: Count of agents.

    """
    return await AgentController().agent_stats_count(
        organization_id, status, current_user
    )


# Agent Swarm
agent_swarm_router = APIRouter(prefix="/{organization_id}/agent-swarm", tags=[APP_TAG])


@agent_swarm_router.post("/create", response_model=AgentSwarmResponseSchema)
async def create_agent_swarm(
    organization_id: UUID,
    request: AgentSwarmCreateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Create a new agent swarm for the current user's organization.

    Args:
        organization_id (UUID): The ID of the organization.
        request (AgentSwarmCreate): The data for creating a new agent swarm.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        AgentSwarmResponseSchema: The created agent swarm's data.

    Raises:
        HTTPException: If there's a duplicate agent swarm or other creation error.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().create_agent_swarm(
            organization_id, request
        )


@agent_swarm_router.get("", response_model=list[AgentSwarmResponseSchema])
async def list_agent_swarms(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List all agent swarms for the current user's organization.

    Args:
        organization_id (UUID): The ID of the organization.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        list[AgentSwarmResponseSchema]: List of agent swarms.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().list_agent_swarms(organization_id)


@agent_swarm_router.put("/{swarm_id}", response_model=AgentSwarmResponseSchema)
async def update_agent_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    request: AgentSwarmUpdateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Update an existing agent swarm.

    Args:
        organization_id (UUID): The ID of the organization.
        swarm_id (UUID): The ID of the swarm to update.
        request (AgentSwarmCreateRequestSchema): The updated swarm data.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        AgentSwarmResponseSchema: The updated agent swarm's data.

    Raises:
        HTTPException: If there's an error updating the swarm.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().update_agent_swarm(
            organization_id, swarm_id, request
        )


@agent_swarm_router.post(
    "/{swarm_id}/add-agent", response_model=AgentSwarmMappingResponseSchema
)
async def add_agent_to_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    request: AgentSwarmMappingCreateRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Add an agent to an existing swarm.

    Args:
        organization_id (UUID): The ID of the organization.
        swarm_id (UUID): The ID of the swarm to add the agent to.
        request (AgentToolRequest): The details of the agent to add.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        AgentResponseSchema: The updated agent's data.

    Raises:
        HTTPException: If there's an error adding the agent to the swarm.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().add_agent_to_swarm(
            organization_id,
            swarm_id,
            request.agent_id,
            request.agent_description,
            request.expected_draft_version,
        )


# list swarm agents
@agent_swarm_router.get(
    "/{swarm_id}/agents", response_model=list[AgentSwarmMappingResponseSchema]
)
async def list_agents_in_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List all agents in a specific swarm.

    Args:
        organization_id (UUID): The ID of the organization.
        swarm_id (UUID): The ID of the swarm to list agents from.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        list[AgentSwarmMappingResponseSchema]: List of agents in the swarm.

    Raises:
        HTTPException: If there's an error retrieving the agents.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().list_agents_in_swarm(
            organization_id, swarm_id
        )


@agent_swarm_router.put(
    "/{swarm_id}/publish",
    response_model=AgentSwarmRevisionResponseSchema,
)
async def publish_agent_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    request: AgentSwarmPublishRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Publish the complete swarm draft as one immutable topology revision."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().publish_agent_swarm(
            organization_id=organization_id,
            swarm_id=swarm_id,
            expected_draft_version=request.expected_draft_version,
            actor_id=current_user.member_id,
        )


@agent_swarm_router.put(
    "/{swarm_id}/unpublish",
    response_model=AgentSwarmResponseSchema,
)
async def withdraw_agent_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Withdraw the alias while existing exact topology refs remain readable."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().withdraw_agent_swarm(
            organization_id=organization_id,
            swarm_id=swarm_id,
        )


@agent_swarm_router.post(
    "/{swarm_id}/revisions/revoke",
    response_model=AgentSwarmRevisionResponseSchema,
)
async def revoke_agent_swarm_revision(
    organization_id: UUID,
    swarm_id: UUID,
    request: AgentSwarmRevokeRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Emergency-revoke one exact topology and request run cancellation."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        return await AgentSwarmController().revoke_agent_swarm_revision(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=request.revision,
            actor_id=current_user.member_id,
            reason=request.reason,
        )


@agent_swarm_router.delete("/{swarm_id}")
async def delete_agent_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Delete an existing agent swarm.

    Args:
        organization_id (UUID): The ID of the organization.
        swarm_id (UUID): The ID of the swarm to delete.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If there's an error deleting the swarm.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        await AgentSwarmController().delete_agent_swarm(
            organization_id,
            swarm_id,
        )
        return {"detail": "Swarm deleted successfully"}


@agent_swarm_router.delete("/{swarm_id}/remove-agent")
async def remove_agent_from_swarm(
    organization_id: UUID,
    swarm_id: UUID,
    request: AgentSwarmMappingDeleteRequestSchema,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Remove an agent from an existing swarm.

    Args:
        organization_id (UUID): The ID of the organization.
        swarm_id (UUID): The ID of the swarm to remove the agent from.
        agent_id (UUID): The ID of the agent to remove.
        current_user (CurrentUserSchema): The authenticated user making the request.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If there's an error removing the agent from the swarm.

    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with _swarm_transaction():
        await AgentSwarmController().remove_agent_from_swarm(
            organization_id,
            swarm_id,
            request.agent_id,
            request.expected_draft_version,
        )
        return {"detail": "Agent removed from swarm successfully"}


background_agent_router = APIRouter(
    prefix="/{organization_id}/agents/{agent_id}/background-agents", tags=[APP_TAG]
)


@background_agent_router.get("", response_model=list[AgentBackgroundAgentInDb])
async def list_background_agents(
    organization_id: UUID,
    agent_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List every background agent attached to this agent, enabled or not."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction(ro=True):
        try:
            return await AgentBackgroundAgentService().list_for_agent(
                agent_id, organization_id
            )
        except AgentNotFoundError:
            raise HTTPException(status_code=404) from None


@background_agent_router.post("", response_model=AgentBackgroundAgentInDb)
async def attach_background_agent(
    organization_id: UUID,
    agent_id: UUID,
    request: AgentBackgroundAgentCreate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Attach a background agent. Always created disabled.

    `enabled` on the request body is ignored: attaching and switching on are
    separate decisions, and the second one goes through PATCH.
    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        try:
            return await AgentBackgroundAgentService().attach(
                agent_id=agent_id,
                background_agent_id=request.background_agent_id,
                organization_id=organization_id,
                expected_draft_version=request.expected_draft_version,
            )
        except AgentNotFoundError:
            raise HTTPException(status_code=404) from None
        except AgentError as error:
            raise HTTPException(status_code=400, detail=str(error))


@background_agent_router.patch(
    "/{background_agent_id}", response_model=AgentBackgroundAgentInDb
)
async def set_background_agent_enabled(
    organization_id: UUID,
    agent_id: UUID,
    background_agent_id: UUID,
    request: AgentBackgroundAgentUpdate,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Enable or disable an existing attachment."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        try:
            attachment = await AgentBackgroundAgentService().set_enabled(
                agent_id=agent_id,
                background_agent_id=background_agent_id,
                organization_id=organization_id,
                enabled=request.enabled,
                expected_draft_version=request.expected_draft_version,
            )
        except AgentNotFoundError:
            raise HTTPException(status_code=404) from None
        except AgentError as error:
            raise HTTPException(status_code=400, detail=str(error))
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


@background_agent_router.delete("/{background_agent_id}", status_code=204)
async def detach_background_agent(
    organization_id: UUID,
    agent_id: UUID,
    background_agent_id: UUID,
    expected_draft_version: Annotated[int, Query(gt=0)],
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """Remove an attachment. The background agent itself is untouched."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
    async with start_transaction():
        try:
            removed = await AgentBackgroundAgentService().detach(
                agent_id=agent_id,
                background_agent_id=background_agent_id,
                organization_id=organization_id,
                expected_draft_version=expected_draft_version,
            )
        except AgentNotFoundError:
            raise HTTPException(status_code=404) from None
    if not removed:
        raise HTTPException(status_code=404, detail="Attachment not found")
