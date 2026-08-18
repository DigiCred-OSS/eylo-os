"""Compose immutable swarm topology rows into executable member snapshots."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.revisions import DefinitionRef
from eylo.modules.agents.domain import (
    InvalidSwarmDefinitionError,
    ResolvedSwarmMember,
    ResolvedSwarmTopology,
)
from eylo.modules.agents.models import AgentKind
from eylo.modules.agents.services.swarm import AgentSwarmRevisionService
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agents.resolver import ExecutableAgentResolver


class ExecutableSwarmResolver:
    """SQL-backed adapter for the shared ResolveExecutableSwarm port."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()
        self._revisions = AgentSwarmRevisionService(self._db)
        self._agents = ExecutableAgentResolver(self._db)

    async def resolve_exact(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedSwarmTopology:
        topology = await self._revisions.get_revision(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=revision,
        )
        member_rows = await self._revisions.list_members(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=revision,
        )
        members: list[ResolvedSwarmMember] = []
        for member_row in member_rows:
            executable = await self._agents.resolve_exact(
                organization_id=organization_id,
                agent_id=member_row.agent_id,
                revision=member_row.agent_revision,
                consumer_kind=consumer_kind,
            )
            if executable.agent.kind is not AgentKind.CONVERSATIONAL:
                raise InvalidSwarmDefinitionError(
                    "A topology member is not a conversational agent."
                )
            members.append(
                ResolvedSwarmMember(
                    executable_agent=executable,
                    description=member_row.agent_description,
                )
            )
        return ResolvedSwarmTopology(
            ref=DefinitionRef(definition_id=swarm_id, revision=revision),
            organization_id=organization_id,
            name=topology.name,
            slug=topology.slug,
            description=topology.description,
            members=tuple(members),
        )

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedSwarmTopology:
        topology = await self._revisions.resolve_for_new_work(
            organization_id=organization_id,
            swarm_id=swarm_id,
        )
        return await self.resolve_exact(
            organization_id=organization_id,
            swarm_id=swarm_id,
            revision=topology.revision,
            consumer_kind=consumer_kind,
        )


def build_executable_swarm_resolver(
    db: AsyncSession | None = None,
) -> ExecutableSwarmResolver:
    return ExecutableSwarmResolver(db)


__all__ = ["ExecutableSwarmResolver", "build_executable_swarm_resolver"]
