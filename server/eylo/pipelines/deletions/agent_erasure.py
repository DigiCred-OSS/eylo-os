"""Agent deactivation composed with exact Agent-memory erasure."""

from __future__ import annotations

from uuid import UUID

from eylo.common.contracts.memory import MemoryLevel, MemoryScope
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.agents.services.indb import AgentService
from eylo.pipelines.deletions.memory_erasure import erase_memory_owner


async def deactivate_agent_and_erase_memory(
    *,
    organization_id: UUID,
    agent_id: UUID,
    service: AgentService | None = None,
) -> AgentInDb | None:
    """Soft-delete one Agent and erase only the facts that Agent owns."""
    agent_service = service or AgentService()
    await agent_service.get_by_organization_and_id(organization_id, agent_id)
    await erase_memory_owner(
        agent_service.repository.db_session,
        MemoryScope(
            organization_id=organization_id,
            level=MemoryLevel.AGENT,
            owner_id=agent_id,
        ),
    )
    return await agent_service.deactivate_agent(agent_id, organization_id)


__all__ = ["deactivate_agent_and_erase_memory"]
