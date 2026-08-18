"""Transport orchestration for the `agents` domain."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.common.schemas import PaginationParams
from eylo.modules.agents.domain import InvalidAgentDefinitionError
from eylo.modules.agents.exceptions import (
    AgentEmailConfigError,
    AgentEmbeddingConfigError,
    AgentError,
    AgentLLMConfigNotFoundError,
    AgentMemoryConfigError,
    AgentNotFoundError,
    AgentRerankingConfigError,
    AgentVoiceConfigError,
    AgentWebRTCConfigError,
)
from eylo.modules.agents.listing import AgentListQuery
from eylo.modules.agents.models import AgentStatus
from eylo.modules.agents.schemas.api import (
    AgentCreateRequestSchema,
    AgentEffectiveVoiceStackResponseSchema,
    AgentResponseSchema,
    AgentSwarmCreateRequestSchema,
    AgentSwarmMappingResponseSchema,
    AgentSwarmResponseSchema,
    AgentSwarmRevisionResponseSchema,
    AgentSwarmUpdateRequestSchema,
    AgentToolRequest,
    AgentUpdateRequestSchema,
    AgentsPaginated,
)
from eylo.modules.agents.schemas.indb import (
    AgentCreate,
    AgentToolCreate,
    AgentToolInDb,
    AgentUpdate,
)
from eylo.modules.agents.services.effective_voice import (
    AgentEffectiveVoiceStackService,
)
from eylo.modules.agents.services.indb import AgentService, AgentToolService
from eylo.modules.agents.services.swarm import (
    AgentSwarmMappingService,
    AgentSwarmRevisionService,
    AgentSwarmService,
)
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.pipelines.deletions.agent_erasure import deactivate_agent_and_erase_memory
from eylo.pipelines.deletions.memory_erasure import MemoryOwnerGraphChanged

logger = logging.getLogger(__name__)


class AgentController:
    """Controller for handling agent-related operations."""

    def __init__(self):
        """Initialize the AgentController."""
        self.service = AgentService()

    async def create_agent(
        self, organization_id: UUID, request: AgentCreateRequestSchema
    ) -> AgentResponseSchema:
        """Create a new agent based on the provided request data."""
        try:
            entity = await self.service.create_(
                AgentCreate(
                    organization_id=organization_id,
                    name=request.name,
                    description=request.description,
                    kind=request.kind,
                    # Public callers create prompt-owned Agents. Registered
                    # first-party implementations enter through internal seeds.
                    implementation=None,
                    llm_provider_config_id=request.llm_provider_config_id,
                    email_provider_config_id=request.email_provider_config_id,
                    webrtc_provider_config_id=request.webrtc_provider_config_id,
                    voice_config_id=request.voice_config_id,
                    reranking_provider_config_id=(
                        request.reranking_provider_config_id
                    ),
                    memory_provider_config_id=request.memory_provider_config_id,
                    allow_file_uploads=request.allow_file_uploads,
                    file_upload_embedding_provider_config_id=(
                        request.file_upload_embedding_provider_config_id
                    ),
                    instruction_template_id=request.instruction_template_id,
                    llm_overrides=request.llm_overrides,
                )
            )
        except (
            AgentEmailConfigError,
            AgentEmbeddingConfigError,
            AgentLLMConfigNotFoundError,
            AgentMemoryConfigError,
            AgentRerankingConfigError,
            AgentVoiceConfigError,
            AgentWebRTCConfigError,
            AgentError,
            InvalidAgentDefinitionError,
            DefinitionRevisionError,
        ) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        return AgentResponseSchema.model_validate(entity)

    async def update_agent_details(
        self,
        agent_id: UUID,
        organization_id: UUID,
        request_payload: AgentUpdateRequestSchema,
    ) -> AgentResponseSchema:
        """Update an existing agent.

        Args:
            agent_id: The ID of the agent to update.
            organization_id: The ID of the organization the agent belongs to.
            request_payload: The payload containing updates.

        Returns:
            AgentResponseSchema: The updated agent.

        Raises:
            HTTPException: If the agent is not found or update fails.

        """
        update_data = AgentUpdate(**request_payload.model_dump(exclude_unset=True))
        try:
            updated_agent_in_db = await self.service.update_agent(
                agent_id=agent_id,
                organization_id=organization_id,
                payload=update_data,
            )
            if not updated_agent_in_db:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent {agent_id} found but update operation failed.",
                )
            return AgentResponseSchema.model_validate(updated_agent_in_db)
        except AgentNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (
            AgentEmailConfigError,
            AgentEmbeddingConfigError,
            AgentLLMConfigNotFoundError,
            AgentMemoryConfigError,
            AgentRerankingConfigError,
            AgentVoiceConfigError,
            AgentWebRTCConfigError,
            AgentError,
            InvalidAgentDefinitionError,
        ) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def deactivate_agent_status(
        self, agent_id: UUID, organization_id: UUID
    ) -> AgentResponseSchema:
        """Deactivate (soft delete) an agent.

        Args:
            agent_id: The ID of the agent to deactivate.
            organization_id: The ID of the organization the agent belongs to.

        Returns:
            AgentResponseSchema: The deactivated agent.

        Raises:
            HTTPException: If the agent is not found or deactivation fails.

        """
        try:
            deactivated_agent_in_db = await deactivate_agent_and_erase_memory(
                agent_id=agent_id,
                organization_id=organization_id,
                service=self.service,
            )
            if not deactivated_agent_in_db:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent {agent_id} found but deactivate operation failed.",
                )
            return AgentResponseSchema.model_validate(deactivated_agent_in_db)
        except AgentNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except MemoryOwnerGraphChanged as error:
            raise HTTPException(
                status_code=409,
                detail="Agent memory changed while deletion was being prepared. Retry.",
            ) from error

    async def update_agent(
        self, organization_id: UUID, agent_id: UUID, request: AgentUpdateRequestSchema
    ) -> AgentResponseSchema:
        """Update an existing agent based on the provided request data."""
        payload = AgentUpdate(**request.model_dump(exclude_unset=True))
        try:
            entity = await self.service.update_agent(
                agent_id=agent_id,
                organization_id=organization_id,
                payload=payload,
            )
        except AgentNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (
            AgentLLMConfigNotFoundError,
            AgentEmailConfigError,
            AgentEmbeddingConfigError,
            AgentMemoryConfigError,
            AgentRerankingConfigError,
            AgentVoiceConfigError,
            AgentWebRTCConfigError,
            AgentError,
            InvalidAgentDefinitionError,
        ) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if entity is None:
            raise HTTPException(status_code=404, detail="Agent update failed.")
        return AgentResponseSchema.model_validate(entity)

    async def get_agent(
        self, agent_id: UUID, organization_id: UUID
    ) -> AgentResponseSchema:
        """Retrieve details of a specific agent.

        Args:
            agent_id (UUID): The ID of the agent to retrieve.
            organization_id (UUID): The ID of the organization the agent belongs to.

        Returns:
            AgentInDb: The agent's details.

        Raises:
            HTTPException: If the agent is not found or the user doesn't have access.

        """
        async with start_transaction(ro=True):
            try:
                service = AgentService()
                agent = await service.get_by_organization_and_id(
                    organization_id=organization_id,
                    pk=agent_id,
                )
                return AgentResponseSchema.model_validate(agent)
            except AgentNotFoundError:
                raise HTTPException(status_code=404)

    async def get_effective_voice_stack(
        self,
        *,
        agent_id: UUID,
        organization_id: UUID,
    ) -> AgentEffectiveVoiceStackResponseSchema:
        async with start_transaction(ro=True):
            try:
                return await AgentEffectiveVoiceStackService().get(
                    organization_id=organization_id,
                    agent_id=agent_id,
                )
            except AgentNotFoundError:
                raise HTTPException(status_code=404) from None

    async def publish_agent(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
        current_user: CurrentUserSchema,
    ) -> AgentResponseSchema:
        if current_user.organization_id != organization_id:
            raise HTTPException(status_code=404)
        async with start_transaction():
            try:
                agent = await AgentService().publish_agent(
                    organization_id=organization_id,
                    agent_id=agent_id,
                    expected_draft_version=expected_draft_version,
                    actor_id=current_user.member_id,
                )
                return AgentResponseSchema.model_validate(agent)
            except AgentNotFoundError:
                raise HTTPException(status_code=404) from None
            except InvalidAgentDefinitionError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            except DefinitionRevisionError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    async def withdraw_agent(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        current_user: CurrentUserSchema,
    ) -> AgentResponseSchema:
        if current_user.organization_id != organization_id:
            raise HTTPException(status_code=404)
        async with start_transaction():
            try:
                agent = await AgentService().withdraw_agent(
                    organization_id=organization_id,
                    agent_id=agent_id,
                )
                return AgentResponseSchema.model_validate(agent)
            except AgentNotFoundError:
                raise HTTPException(status_code=404) from None
            except DefinitionRevisionError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    async def revoke_agent_revision(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
        reason: str,
        current_user: CurrentUserSchema,
    ) -> AgentResponseSchema:
        if current_user.organization_id != organization_id:
            raise HTTPException(status_code=404)
        async with start_transaction():
            from eylo.modules.agents.services.revisions import AgentRevisionService

            try:
                service = AgentService()
                await AgentRevisionService(service.repository.db_session).revoke(
                    organization_id=organization_id,
                    agent_id=agent_id,
                    revision=revision,
                    actor_id=current_user.member_id,
                    reason=reason,
                )
                agent = await service.get_by_organization_and_id(
                    organization_id,
                    agent_id,
                )
                return AgentResponseSchema.model_validate(agent)
            except AgentNotFoundError:
                raise HTTPException(status_code=404) from None
            except DefinitionRevisionError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    async def list_agents(
        self,
        organization_id: UUID,
        pagination: PaginationParams,
        current_user: CurrentUserSchema,
        filters: AgentListQuery | None = None,
    ) -> AgentsPaginated:
        """List agents for an organization.

        If filters.agent_ids is provided, returns only those specific agents.
        Useful for bulk fetching agents by ID to avoid N+1 queries.
        """
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=404)

        async with start_transaction(ro=True):
            try:
                service = AgentService()

                # Bulk ID lookup retains its all-requested-IDs behavior while
                # composing the same filters and stable ordering as the list.
                if filters and filters.agent_ids:
                    requested_limit = len(set(filters.agent_ids))
                    agents = await service.list_by_organization(
                        organization_id,
                        limit=requested_limit,
                        filters=filters,
                    )
                    count = await service.count_by_organization(
                        organization_id,
                        filters=filters,
                    )
                    return AgentsPaginated(
                        data=agents,
                        total=count,
                        limit=requested_limit,
                        page=1,
                    )

                # Otherwise, paginated list
                agents = await service.list_by_organization(
                    organization_id,
                    limit=pagination.limit,
                    offset=pagination.get_offset(),
                    filters=filters,
                )
                count = await service.count_by_organization(
                    organization_id,
                    filters=filters,
                )
                return AgentsPaginated(
                    data=agents,
                    total=count,
                    limit=pagination.limit,
                    page=pagination.page,
                )
            except AgentNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))

    async def assign_tool_to_agent(
        self,
        organization_id: UUID,
        agent_id: UUID,
        request: AgentToolRequest,
        current_user: CurrentUserSchema,
    ) -> AgentToolInDb:
        """Assign a tool to an agent."""
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        async with start_transaction():
            service = AgentToolService()
            try:
                agent = await AgentService().get_by_organization_and_id(
                    organization_id=organization_id,
                    pk=agent_id,
                )
            except AgentNotFoundError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

            # Auto-materialize system tools that only exist in the registry
            from eylo.modules.tools.services.indb import ToolService

            tool = await ToolService().ensure_system_tool_exists(
                request.tool_id, organization_id
            )

            # Enforce cross-organization isolation: a tool that exists in another
            # org must not be assignable here. ensure_system_tool_exists returns
            # the existing row without an org check, so we validate explicitly.
            if tool is None or tool.organization_id != organization_id:
                logger.warning(
                    "Cross-org tool assignment blocked",
                    extra={
                        "member_id": str(current_user.member_id),
                        "organization_id": str(organization_id),
                        "agent_id": str(agent_id),
                        "tool_id": str(request.tool_id),
                        "tool_org_id": str(tool.organization_id) if tool else None,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tool not found.",
                )

            from eylo.modules.tools.services.tool_register import system_tool_id

            memory_tool_ids = {
                system_tool_id("memory_forget", organization_id),
                system_tool_id("memory_recall", organization_id),
                system_tool_id("memory_refresh", organization_id),
                system_tool_id("memory_remember", organization_id),
            }
            if (
                request.tool_id in memory_tool_ids
                and agent.memory_provider_config_id is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Assign a memory config before adding memory tools."
                    ),
                )

            existing_assignment = await service.get_by_agent_and_tool(
                agent_id,
                request.tool_id,
            )
            if existing_assignment:
                return existing_assignment

            tool_revision = await ToolService().resolve_for_new_work(
                organization_id=organization_id,
                tool_id=request.tool_id,
            )

            result = await service.create_(
                AgentToolCreate(
                    agent_id=agent.id,
                    tool_id=request.tool_id,
                    tool_revision=tool_revision.revision,
                    organization_id=organization_id,
                )
            )
            from eylo.modules.agents.services.revisions import AgentRevisionService

            await AgentRevisionService(service.repository.db_session).mark_draft_changed(
                organization_id=organization_id,
                agent_id=agent.id,
                expected_draft_version=request.expected_draft_version,
            )
            return result

    async def agent_stats_count(
        self,
        organization_id: UUID,
        status: list[str] | None,
        current_user: CurrentUserSchema,
    ) -> int:
        """Get count of agents, optionally filtered by status."""
        if organization_id != current_user.organization_id:
            raise HTTPException(status_code=404)

        filters = (
            AgentListQuery(
                statuses=tuple(
                    AgentStatus(value)
                    for value in status
                    if value in AgentStatus.__members__
                )
            )
            if status
            else None
        )

        async with start_transaction(ro=True):
            try:
                service = AgentService()
                agent_count = await service.count_by_organization(
                    organization_id,
                    filters=filters,
                )
                return agent_count
            except AgentNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))

    async def list_agent_tools(self, agent_id: UUID, organization_id: UUID):
        """List all tools for a given agent."""
        async with start_transaction(ro=True):
            try:
                await self.service.get_by_organization_and_id(
                    organization_id=organization_id,
                    pk=agent_id,
                )
            except AgentNotFoundError:
                raise HTTPException(status_code=404)
            return await AgentToolService().list_tools_for_agent(
                agent_id, organization_id
            )

    async def remove_tool_from_agent(
        self,
        agent_id: UUID,
        tool_id: UUID,
        organization_id: UUID,
        expected_draft_version: int,
    ):
        """Remove a tool from an agent."""
        async with start_transaction():
            try:
                await self.service.get_by_organization_and_id(
                    organization_id=organization_id,
                    pk=agent_id,
                )
            except AgentNotFoundError:
                raise HTTPException(status_code=404)
            service = AgentToolService()
            await service.remove_tool_from_agent(agent_id, tool_id)
            from eylo.modules.agents.services.revisions import AgentRevisionService

            await AgentRevisionService(service.repository.db_session).mark_draft_changed(
                organization_id=organization_id,
                agent_id=agent_id,
                expected_draft_version=expected_draft_version,
            )


class AgentSwarmController:
    """Controller for handling agent swarm-related operations."""

    def __init__(self):
        """Initialize the AgentSwarmController."""
        self.service = AgentSwarmService()
        self.agent_mapping_service = AgentSwarmMappingService()
        self.revision_service = AgentSwarmRevisionService()

    async def list_agent_swarms(self, organization_id: UUID):
        """List all agent swarms for the given organization."""
        swarms = await self.service.list_by_organization(organization_id)
        return [AgentSwarmResponseSchema.model_validate(swarm) for swarm in swarms]

    async def create_agent_swarm(
        self, organization_id: UUID, request: AgentSwarmCreateRequestSchema
    ):
        """Create a new agent swarm based on the provided request data."""
        entity = await self.service.create(
            organization_id=organization_id,
            name=request.name,
            description=request.description or "",
        )
        return AgentSwarmResponseSchema.model_validate(entity)

    async def update_agent_swarm(
        self,
        organization_id: UUID,
        swarm_id: UUID,
        request: AgentSwarmUpdateRequestSchema,
    ):
        """Update an existing agent swarm based on the provided request data."""
        entity = await self.service.update(
            pk=swarm_id,
            organization_id=organization_id,
            expected_draft_version=request.expected_draft_version,
            name=request.name,
            description=request.description,
        )
        return AgentSwarmResponseSchema.model_validate(entity)

    async def delete_agent_swarm(
        self,
        organization_id: UUID,
        swarm_id: UUID,
    ) -> None:
        await self.service.delete_draft(
            organization_id=organization_id,
            swarm_id=swarm_id,
        )

    async def add_agent_to_swarm(
        self,
        organization_id: UUID,
        swarm_id: UUID,
        agent_id: UUID,
        agent_description: Optional[str],
        expected_draft_version: int,
    ):
        """Add an agent to a swarm."""
        entity = await self.agent_mapping_service.create(
            organization_id=organization_id,
            swarm_id=swarm_id,
            agent_id=agent_id,
            agent_description=agent_description,
            expected_draft_version=expected_draft_version,
        )
        return entity

    async def list_agents_in_swarm(
        self,
        organization_id: UUID,
        swarm_id: UUID,
    ):
        """List all agents in a given swarm."""
        mappings = await self.agent_mapping_service.list_by_swarm_id(
            swarm_id=swarm_id, organization_id=organization_id
        )
        return [
            AgentSwarmMappingResponseSchema.model_validate(mapping)
            for mapping in mappings
        ]

    async def remove_agent_from_swarm(
        self,
        organization_id: UUID,
        swarm_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
    ) -> None:
        await self.agent_mapping_service.delete_agent_from_swarm(
            agent_id=agent_id,
            swarm_id=swarm_id,
            organization_id=organization_id,
            expected_draft_version=expected_draft_version,
        )

    async def publish_agent_swarm(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        expected_draft_version: int,
        actor_id: UUID,
    ) -> AgentSwarmRevisionResponseSchema:
        row = await self.revision_service.publish(
            organization_id=organization_id,
            swarm_id=swarm_id,
            expected_draft_version=expected_draft_version,
            actor_id=actor_id,
        )
        return AgentSwarmRevisionResponseSchema.model_validate(row)

    async def withdraw_agent_swarm(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
    ) -> AgentSwarmResponseSchema:
        row = await self.revision_service.withdraw(
            organization_id=organization_id,
            swarm_id=swarm_id,
        )
        return AgentSwarmResponseSchema.model_validate(row)

    async def revoke_agent_swarm_revision(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> AgentSwarmRevisionResponseSchema:
        row = await self.revision_service.revoke(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=revision,
            actor_id=actor_id,
            reason=reason,
        )
        return AgentSwarmRevisionResponseSchema.model_validate(row)
