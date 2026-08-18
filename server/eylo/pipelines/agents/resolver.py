"""Resolve one exact executable agent for every runtime surface."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.revisions import DefinitionRef
from eylo.modules.agents.domain import (
    InvalidAgentDefinitionError,
    ResolvedExecutableAgent,
)
from eylo.modules.agents.models import AgentKind, AgentStatus
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.agents.services.revisions import AgentRevisionService
from eylo.modules.integrations_v2.services.installations import (
    CuratedIntegrationService,
)
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.modules.templates.service import TemplateService
from eylo.modules.tools.services.indb import ToolService
from eylo.pipelines.integrations_v2.agent_tools import project_curated_tools


class ExecutableAgentResolver:
    """SQL-backed adapter for the shared ResolveExecutableAgent port."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()
        self._revisions = AgentRevisionService(self._db)

    async def resolve_exact(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedExecutableAgent:
        row = await self._revisions.get_revision(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
        )
        if row.instruction_template_id is None:
            system_prompt = None
            prompt_segments = ()
        else:
            rendered = await TemplateService(self._db).render_exact(
                organization_id=organization_id,
                template_id=row.instruction_template_id,
                revision=row.instruction_template_revision,
                consumer_kind=consumer_kind,
                values={},
            )
            system_prompt = rendered.text
            prompt_segments = rendered.segments

        tool_refs = await self._revisions.list_tool_refs(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
        )
        tools = await ToolService(self._db).list_exact(
            refs=tool_refs,
            organization_id=organization_id,
        )
        if len(tools) != len(tool_refs):
            raise InvalidAgentDefinitionError(
                "An exact agent revision contains an unavailable tool grant."
            )

        # Curated tools are resolved separately because their contract lives in
        # the registry rather than a revision row. A grant whose binding this
        # deployment no longer carries is dropped by the projection. Persisted
        # platform/MCP grants fail the whole Agent when an exact revision is absent.
        curated_ids = await self._revisions.list_curated_tool_ids(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
        )
        curated_rows = await CuratedIntegrationService(
            self._db
        ).list_offerable_tools(
            organization_id=organization_id,
            tool_ids=curated_ids,
        )
        curated_tools = project_curated_tools(rows=curated_rows)
        background_refs = await self._revisions.list_background_refs(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
        )
        return ResolvedExecutableAgent(
            ref=DefinitionRef(definition_id=agent_id, revision=revision),
            agent=_to_agent(row),
            consumer_kind=consumer_kind,
            system_prompt=system_prompt,
            prompt_segments=prompt_segments,
            tools=(*tools, *curated_tools),
            background_agents=tuple(
                DefinitionRef(
                    definition_id=background_agent_id,
                    revision=background_revision,
                )
                for background_agent_id, background_revision in background_refs
            ),
            voice_config=row.voice_config,
        )

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedExecutableAgent:
        row = await self._revisions.resolve_for_new_work(
            organization_id=organization_id,
            agent_id=agent_id,
        )
        return await self.resolve_exact(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=row.revision,
            consumer_kind=consumer_kind,
        )


def _to_agent(row) -> AgentInDb:
    return AgentInDb(
        id=row.agent_id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        webhook=row.webhook,
        status=AgentStatus.ACTIVE,
        kind=AgentKind(row.kind),
        implementation=row.implementation,
        organization_id=row.organization_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted=row.deleted,
        external_id=row.external_id,
        llm_provider_config_id=row.llm_provider_config_id,
        llm_provider_config_revision=row.llm_provider_config_revision,
        email_provider_config_id=row.email_provider_config_id,
        email_provider_config_revision=row.email_provider_config_revision,
        webrtc_provider_config_id=row.webrtc_provider_config_id,
        webrtc_provider_config_revision=row.webrtc_provider_config_revision,
        voice_config_id=row.voice_config_id,
        voice_config_revision=row.voice_config_revision,
        reranking_provider_config_id=row.reranking_provider_config_id,
        reranking_provider_config_revision=row.reranking_provider_config_revision,
        memory_provider_config_id=row.memory_provider_config_id,
        memory_provider_config_revision=row.memory_provider_config_revision,
        allow_file_uploads=row.allow_file_uploads,
        file_upload_embedding_provider_config_id=(
            row.file_upload_embedding_provider_config_id
        ),
        file_upload_embedding_provider_config_revision=(
            row.file_upload_embedding_provider_config_revision
        ),
        instruction_template_id=row.instruction_template_id,
        llm_overrides=row.llm_overrides,
        prompt=None,
        lifecycle="published",
        published_revision=row.revision,
        draft_version=1,
        draft_dirty=False,
    )


def build_executable_agent_resolver(
    db: AsyncSession | None = None,
) -> ExecutableAgentResolver:
    return ExecutableAgentResolver(db)


__all__ = ["ExecutableAgentResolver", "build_executable_agent_resolver"]
