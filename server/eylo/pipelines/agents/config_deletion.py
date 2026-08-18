"""Block provider-config deletion while an agent definition references it."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agents.models import AgentRevisionModel, AgentsModel
from eylo.modules.email_configs.wiring import build_email_config_service
from eylo.modules.llm_configs.wiring import build_llm_config_service
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.webrtc_configs.wiring import build_webrtc_config_service
from eylo.pipelines.memory.dependency_references import (
    CombinedProviderConfigReferences,
    MemoryDependencyReferenceLookup,
)

_REFERENCE_COLUMNS = {
    Capability.LLM: (
        AgentsModel.llm_provider_config_id,
        AgentRevisionModel.llm_provider_config_id,
    ),
    Capability.EMAIL: (
        AgentsModel.email_provider_config_id,
        AgentRevisionModel.email_provider_config_id,
    ),
    Capability.WEBRTC: (
        AgentsModel.webrtc_provider_config_id,
        AgentRevisionModel.webrtc_provider_config_id,
    ),
}


class AgentConfigReferenceLookup:
    def __init__(self, db: AsyncSession, capability: Capability) -> None:
        self._db = db
        self._header_column, self._revision_column = _REFERENCE_COLUMNS[capability]

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model, column in (
            (AgentsModel, self._header_column),
            (AgentRevisionModel, self._revision_column),
        ):
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        column == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


async def delete_agent_bound_config(
    *,
    organization_id: UUID,
    config_id: UUID,
    capability: Capability,
) -> None:
    """Delete one config only after checking its owning agent binding."""
    async with start_transaction() as db:
        references = AgentConfigReferenceLookup(db, capability)
        if capability is Capability.LLM:
            service = build_llm_config_service(
                db,
                references=CombinedProviderConfigReferences(
                    references,
                    MemoryDependencyReferenceLookup(db, Capability.LLM),
                ),
            )
        elif capability is Capability.EMAIL:
            service = build_email_config_service(db, references=references)
        elif capability is Capability.WEBRTC:
            service = build_webrtc_config_service(db, references=references)
        else:  # pragma: no cover - closed internal call set
            raise ValueError("Capability is not agent-bound here.")
        await service.delete(
            organization_id=organization_id,
            config_id=config_id,
        )
