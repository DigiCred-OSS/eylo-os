"""Agent-scoped LLM readiness checks for request ingress."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agents.models import AgentStatus
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.agents.services.indb import AgentService
from eylo.modules.llm_configs.domain import ResolvedLLM
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError


class AgentLLMReadinessService:
    """Resolve an agent's effective LLM config without invoking a provider."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        *,
        agents: AgentService | None = None,
        resolver: LLMConfigResolver | None = None,
    ) -> None:
        self._db = db
        self._agents = agents or AgentService(db)
        self._resolver = resolver

    async def ensure_agent_ready(
        self,
        organization_id: UUID,
        agent_id: UUID,
    ) -> ResolvedLLM:
        agent = await self._agents.get_by_organization_and_id(
            organization_id=organization_id,
            pk=agent_id,
        )
        return await self.ensure_ready(agent)

    async def ensure_ready(self, agent: AgentInDb) -> ResolvedLLM:
        if agent.status is not AgentStatus.ACTIVE:
            raise NotConfiguredError(
                capability=Capability.LLM,
                missing=["published_agent"],
                configure_via=f"/api/agents/{agent.id}",
            )
        if (
            agent.llm_provider_config_id is None
            or agent.llm_provider_config_revision is None
        ):
            raise NotConfiguredError(
                capability=Capability.LLM,
                missing=["provider_config", "provider_config_revision"],
                configure_via=f"/api/agents/{agent.id}",
            )
        resolver = self._resolver
        if resolver is None:
            resolver = build_llm_config_resolver(self._db)
        return await resolver.resolve_llm_pinned(
            agent.organization_id,
            provider_config_id=agent.llm_provider_config_id,
            revision=agent.llm_provider_config_revision,
            overrides=agent.llm_overrides.model_dump(exclude_none=True),
        )
