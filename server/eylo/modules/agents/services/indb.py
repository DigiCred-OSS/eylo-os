"""Application services for the `agents` domain."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.revisions import DefinitionHeaderState, DefinitionLifecycle
from eylo.common.services import EyloBaseService
from eylo.modules.agents.domain import InvalidAgentDefinitionError
from eylo.modules.agents.exceptions import (
    AgentEmailConfigError,
    AgentEmbeddingConfigError,
    AgentLLMConfigNotFoundError,
    AgentMemoryConfigError,
    AgentNotFoundError,
    AgentRerankingConfigError,
    AgentVoiceConfigError,
    AgentWebRTCConfigError,
)
from eylo.modules.agents.kinds import assert_implementation_is_valid
from eylo.modules.agents.listing import (
    AgentListQuery,
    AgentSortDirection,
    AgentSortField,
)
from eylo.modules.agents.models import AgentKind, AgentStatus, AgentToolMappingModal
from eylo.modules.agents.repositories import (
    AgentToolMappingRepository,
    AgentsRepository,
)
from eylo.modules.agents.schemas.indb import (
    AgentCreate,
    AgentInDb,
    AgentToolCreate,
    AgentToolInDb,
    AgentUpdate,
)
from eylo.modules.email_configs.domain import InvalidEmailConfig
from eylo.modules.email_configs.resolver import EmailConfigResolver
from eylo.modules.email_configs.service import EmailConfigService
from eylo.modules.email_configs.wiring import build_email_config_service
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.embedding_configs.resolver import EmbeddingConfigResolver
from eylo.modules.embedding_configs.service import EmbeddingConfigService
from eylo.modules.embedding_configs.wiring import build_embedding_config_service
from eylo.modules.llm_configs.domain import InvalidLLMConfig
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.schemas import LLMOverridesSchema
from eylo.modules.llm_configs.service import LLMConfigService
from eylo.modules.llm_configs.wiring import build_llm_config_service
from eylo.modules.memory_configs.domain import InvalidMemoryConfig
from eylo.modules.memory_configs.resolver import MemoryConfigResolver
from eylo.modules.memory_configs.service import MemoryConfigService
from eylo.modules.memory_configs.wiring import build_memory_config_service
from eylo.modules.provider_configs.domain import ProviderConfigNotFound
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.reranking_configs.domain import InvalidRerankingConfig
from eylo.modules.reranking_configs.resolver import RerankingConfigResolver
from eylo.modules.reranking_configs.service import RerankingConfigService
from eylo.modules.reranking_configs.wiring import build_reranking_config_service
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.services.indb import ToolService
from eylo.modules.tools.services.tool_register import system_tool_id
from eylo.modules.voice.exceptions import VoiceConfigNotFound
from eylo.modules.voice.services.voice_configs import VoiceConfigService
from eylo.modules.webrtc_configs.domain import InvalidWebRTCConfig
from eylo.modules.webrtc_configs.resolver import WebRTCConfigResolver
from eylo.modules.webrtc_configs.service import WebRTCConfigService
from eylo.modules.webrtc_configs.wiring import build_webrtc_config_service

_MEMORY_TOOL_NAMES = (
    "memory_forget",
    "memory_recall",
    "memory_refresh",
    "memory_remember",
)
_EMAIL_TOOL_NAMES = ("send_email",)
_KNOWLEDGE_TOOL_NAMES = ("kb_query", "kb_write_destinations", "kb_write")


def _escape_like(value: str) -> str:
    """Escape user text before placing it inside an ILIKE contains pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class AgentService(EyloBaseService[AgentInDb]):
    """AgentService behavior for the "agents" domain."""

    @property
    def schema(self) -> AgentInDb:
        """Schema for the "agents" domain."""
        return AgentInDb

    @property
    def repository(self) -> AgentsRepository:
        """Repository for the "agents" domain."""
        return self._repository

    @repository.setter
    def repository(self, value: AgentsRepository):
        """Repository for the "agents" domain."""
        self._repository = value

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        llm_configs: LLMConfigService | None = None,
        email_configs: EmailConfigService | None = None,
        webrtc_configs: WebRTCConfigService | None = None,
        reranking_configs: RerankingConfigService | None = None,
        memory_configs: MemoryConfigService | None = None,
        embedding_configs: EmbeddingConfigService | None = None,
    ):
        """Initialize agent persistence and optional LLM config validation."""
        self._repository = AgentsRepository(db)
        self._db = db
        self._llm_configs = llm_configs
        self._email_configs = email_configs
        self._webrtc_configs = webrtc_configs
        self._reranking_configs = reranking_configs
        self._memory_configs = memory_configs
        self._embedding_configs = embedding_configs

    def orm_to_schema(self, orm_object) -> AgentInDb:
        """Convert ORM Model to Schema."""
        return AgentInDb(
            id=orm_object.id,
            name=orm_object.name,
            slug=orm_object.slug,
            description=orm_object.description,
            webhook=orm_object.webhook,
            status=orm_object.status,
            kind=orm_object.kind,
            implementation=orm_object.implementation,
            organization_id=orm_object.organization_id,
            created_at=orm_object.created_at,
            updated_at=orm_object.updated_at,
            deleted=orm_object.deleted,
            external_id=orm_object.external_id,
            llm_provider_config_id=orm_object.llm_provider_config_id,
            llm_provider_config_revision=orm_object.llm_provider_config_revision,
            email_provider_config_id=orm_object.email_provider_config_id,
            email_provider_config_revision=orm_object.email_provider_config_revision,
            webrtc_provider_config_id=orm_object.webrtc_provider_config_id,
            webrtc_provider_config_revision=orm_object.webrtc_provider_config_revision,
            voice_config_id=orm_object.voice_config_id,
            voice_config_revision=orm_object.voice_config_revision,
            reranking_provider_config_id=orm_object.reranking_provider_config_id,
            reranking_provider_config_revision=(
                orm_object.reranking_provider_config_revision
            ),
            memory_provider_config_id=orm_object.memory_provider_config_id,
            memory_provider_config_revision=orm_object.memory_provider_config_revision,
            allow_file_uploads=orm_object.allow_file_uploads,
            file_upload_embedding_provider_config_id=(
                orm_object.file_upload_embedding_provider_config_id
            ),
            file_upload_embedding_provider_config_revision=(
                orm_object.file_upload_embedding_provider_config_revision
            ),
            instruction_template_id=orm_object.instruction_template_id,
            llm_overrides=LLMOverridesSchema.model_validate(
                orm_object.llm_overrides or {}
            ),
            prompt=orm_object.prompt,
            lifecycle=orm_object.lifecycle,
            published_revision=orm_object.published_revision,
            draft_version=orm_object.draft_version,
            draft_dirty=orm_object.draft_dirty,
        )

    async def get_(self, pk: UUID) -> AgentInDb:
        """Get Agent by ID."""
        agent = await self.repository.get_(pk)
        if not agent:
            raise AgentNotFoundError(f"{pk=} not found")
        return self.orm_to_schema(agent)

    async def create_(self, request: AgentCreate) -> AgentInDb:
        """Create New Agent."""
        await self._validate_llm_config_reference(
            request.organization_id,
            request.llm_provider_config_id,
        )
        await self._validate_email_config_reference(
            request.organization_id,
            request.email_provider_config_id,
        )
        await self._validate_webrtc_config_reference(
            request.organization_id,
            request.webrtc_provider_config_id,
        )
        voice_config_revision = await self._validate_voice_config_reference(
            organization_id=request.organization_id,
            agent_kind=request.kind,
            config_id=request.voice_config_id,
        )
        await self._validate_reranking_config_reference(
            request.organization_id,
            request.reranking_provider_config_id,
        )
        await self._validate_memory_config_reference(
            request.organization_id,
            request.memory_provider_config_id,
        )
        await self._validate_file_upload_configuration(
            organization_id=request.organization_id,
            allow_file_uploads=request.allow_file_uploads,
            config_id=request.file_upload_embedding_provider_config_id,
        )
        await self._validate_instruction_template_reference(
            request.organization_id,
            request.instruction_template_id,
        )
        assert_implementation_is_valid(request.kind, request.implementation)
        request = request.model_copy(
            update={"voice_config_revision": voice_config_revision}
        )
        agent = await self.repository.create(request)
        return self.orm_to_schema(agent)

    async def get_by_organization_and_id(
        self, organization_id: UUID, pk: UUID
    ) -> AgentInDb:
        """Get Agent by Organization and ID."""
        agent_model = await self.repository.get_by_id_and_organization(
            pk=pk, organization_id=organization_id
        )
        if not agent_model:
            # This case should ideally be covered if repository method returns None
            # and controller translates, or repository raises specific not_found.
            # For now, aligning with existing pattern of service raising.
            raise AgentNotFoundError(
                f"Agent with id {pk} not found in organization {organization_id}"
            )
        return self.orm_to_schema(agent_model)

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        filters: AgentListQuery | None = None,
    ) -> list[AgentInDb]:
        """List Agents by Organization."""
        query_filters = self._agent_list_filters(organization_id, filters)
        agents = await self.repository.filter_(
            query_filters,
            limit=limit,
            offset=offset,
            order_by=self._agent_list_order(filters),
        )
        return self.orm_to_schema_list(agents)

    async def list_by_ids(
        self,
        agent_ids: List[UUID],
        organization_id: UUID,
    ) -> list[AgentInDb]:
        """Bulk Fetch Agents by IDs."""
        agents = await self.repository.list_by_ids(
            agent_ids=agent_ids,
            organization_id=organization_id,
        )
        return self.orm_to_schema_list(agents)

    async def list_agents(
        self, organization_id: UUID, include_inactive: bool = False
    ) -> List[AgentInDb]:
        """List Agents by Organization (with status filtering)."""
        agent_models = await self.repository.list_by_organization_id(
            organization_id=organization_id, include_inactive=include_inactive
        )
        return self.orm_to_schema_list(agent_models)

    async def update_agent(
        self,
        agent_id: UUID,
        organization_id: UUID,
        payload: AgentUpdate,
    ) -> Optional[AgentInDb]:
        """Edit the mutable draft."""
        existing = await self.get_by_organization_and_id(
            organization_id=organization_id, pk=agent_id
        )
        fields = set(payload.model_fields_set)
        if payload.expected_draft_version is None:
            raise InvalidAgentDefinitionError(
                "expected_draft_version is required to edit an agent draft."
            )
        if fields == {"expected_draft_version"}:
            raise InvalidAgentDefinitionError("Agent draft update is empty.")
        forbidden_revision_fields = {
            field
            for field in fields
            if field.endswith("_provider_config_revision")
        }
        if forbidden_revision_fields:
            raise InvalidAgentDefinitionError(
                "Provider revisions are resolved only when the agent is published."
            )
        if "implementation" in payload.model_fields_set:
            assert_implementation_is_valid(existing.kind, payload.implementation)
        llm_binding_changed = "llm_provider_config_id" in payload.model_fields_set
        if llm_binding_changed:
            await self._validate_llm_config_reference(
                organization_id,
                payload.llm_provider_config_id,
            )
        email_binding_changed = "email_provider_config_id" in payload.model_fields_set
        if email_binding_changed:
            await self._validate_email_config_reference(
                organization_id,
                payload.email_provider_config_id,
            )
        webrtc_binding_changed = (
            "webrtc_provider_config_id" in payload.model_fields_set
        )
        if webrtc_binding_changed:
            await self._validate_webrtc_config_reference(
                organization_id,
                payload.webrtc_provider_config_id,
            )
        voice_binding_changed = "voice_config_id" in payload.model_fields_set
        voice_config_revision = existing.voice_config_revision
        if voice_binding_changed:
            voice_config_revision = await self._validate_voice_config_reference(
                organization_id=organization_id,
                agent_kind=existing.kind,
                config_id=payload.voice_config_id,
            )
        reranking_binding_changed = (
            "reranking_provider_config_id" in payload.model_fields_set
        )
        if reranking_binding_changed:
            await self._validate_reranking_config_reference(
                organization_id,
                payload.reranking_provider_config_id,
            )
        memory_binding_changed = (
            "memory_provider_config_id" in payload.model_fields_set
        )
        if memory_binding_changed:
            await self._validate_memory_config_reference(
                organization_id,
                payload.memory_provider_config_id,
            )
        upload_embedding_binding_changed = (
            "file_upload_embedding_provider_config_id" in payload.model_fields_set
        )
        next_allow_file_uploads = (
            payload.allow_file_uploads
            if "allow_file_uploads" in payload.model_fields_set
            else existing.allow_file_uploads
        )
        next_upload_embedding_config_id = (
            payload.file_upload_embedding_provider_config_id
            if upload_embedding_binding_changed
            else existing.file_upload_embedding_provider_config_id
        )
        await self._validate_file_upload_configuration(
            organization_id=organization_id,
            allow_file_uploads=bool(next_allow_file_uploads),
            config_id=next_upload_embedding_config_id,
        )
        if "instruction_template_id" in payload.model_fields_set:
            await self._validate_instruction_template_reference(
                organization_id,
                payload.instruction_template_id,
            )

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude={"expected_draft_version"},
        )
        if llm_binding_changed:
            update_data["llm_provider_config_revision"] = None
        if email_binding_changed:
            update_data["email_provider_config_revision"] = None
        if webrtc_binding_changed:
            update_data["webrtc_provider_config_revision"] = None
        if voice_binding_changed:
            update_data["voice_config_revision"] = voice_config_revision
        if reranking_binding_changed:
            update_data["reranking_provider_config_revision"] = None
        if memory_binding_changed:
            update_data["memory_provider_config_revision"] = None
        if upload_embedding_binding_changed:
            update_data["file_upload_embedding_provider_config_revision"] = None
        payload = AgentUpdate.model_validate(
            {
                **update_data,
                "expected_draft_version": payload.expected_draft_version,
            }
        )
        updated_agent_model = await self.repository.update_(
            agent_id=agent_id, organization_id=organization_id, payload=payload
        )
        if updated_agent_model is None:
            return None
        state = DefinitionHeaderState(
            lifecycle=DefinitionLifecycle(updated_agent_model.lifecycle),
            published_revision=updated_agent_model.published_revision,
            draft_version=updated_agent_model.draft_version,
            draft_dirty=updated_agent_model.draft_dirty,
        ).edit(expected_draft_version=payload.expected_draft_version)
        updated_agent_model.lifecycle = state.lifecycle.value
        updated_agent_model.published_revision = state.published_revision
        updated_agent_model.draft_version = state.draft_version
        updated_agent_model.draft_dirty = state.draft_dirty
        updated_agent_model = await self.repository.save_(updated_agent_model)
        return self.orm_to_schema(updated_agent_model)

    async def publish_agent(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
        actor_id: UUID | None = None,
    ) -> AgentInDb:
        from eylo.modules.agents.services.revisions import AgentRevisionService

        await AgentRevisionService(self.repository.db_session).publish(
            organization_id=organization_id,
            agent_id=agent_id,
            expected_draft_version=expected_draft_version,
            actor_id=actor_id,
        )
        return await self.get_by_organization_and_id(organization_id, agent_id)

    async def withdraw_agent(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
    ) -> AgentInDb:
        from eylo.modules.agents.services.revisions import AgentRevisionService

        row = await AgentRevisionService(self.repository.db_session).withdraw(
            organization_id=organization_id,
            agent_id=agent_id,
        )
        return self.orm_to_schema(row)

    async def deactivate_agent(
        self, agent_id: UUID, organization_id: UUID
    ) -> Optional[AgentInDb]:
        """Deactivate Agent (Soft Delete)."""
        existing = await self.get_by_organization_and_id(organization_id, agent_id)
        if existing.published_revision is not None:
            await self.withdraw_agent(
                organization_id=organization_id,
                agent_id=agent_id,
            )
        model = await self.repository.get_by_id_and_organization(
            pk=agent_id,
            organization_id=organization_id,
        )
        if model is None:
            return None
        model.deleted = True
        model.status = AgentStatus.INACTIVE
        return self.orm_to_schema(await self.repository.save_(model))

    async def count_by_organization(
        self,
        organization_id: UUID,
        filters: AgentListQuery | None = None,
    ) -> int:
        return await self.repository.count_(
            self._agent_list_filters(organization_id, filters)
        )

    def _agent_list_filters(
        self,
        organization_id: UUID,
        filters: AgentListQuery | None,
    ) -> list:
        model = self.repository.model
        query_filters = [
            model.organization_id == organization_id,
            model.deleted.is_(False),
        ]
        if filters is None:
            return query_filters
        if filters.agent_ids:
            query_filters.append(model.id.in_(filters.agent_ids))
        if filters.search:
            pattern = f"%{_escape_like(filters.search)}%"
            query_filters.append(
                or_(
                    model.name.ilike(pattern, escape="\\"),
                    model.slug.ilike(pattern, escape="\\"),
                    model.description.ilike(pattern, escape="\\"),
                )
            )
        if filters.statuses:
            query_filters.append(model.status.in_(filters.statuses))
        if filters.kinds:
            query_filters.append(model.kind.in_(filters.kinds))
        return query_filters

    def _agent_list_order(
        self,
        filters: AgentListQuery | None,
    ) -> list:
        model = self.repository.model
        sort_by = filters.sort_by if filters else AgentSortField.UPDATED_AT
        direction = filters.sort_direction if filters else AgentSortDirection.DESC
        sort_columns = {
            AgentSortField.NAME: model.name,
            AgentSortField.STATUS: model.status,
            AgentSortField.KIND: model.kind,
            AgentSortField.CREATED_AT: model.created_at,
            AgentSortField.UPDATED_AT: model.updated_at,
        }
        primary = sort_columns[sort_by]
        ordered = (
            primary.asc() if direction is AgentSortDirection.ASC else primary.desc()
        )
        return [ordered, model.id.asc()]

    async def _validate_llm_config_reference(
        self,
        organization_id: UUID,
        config_id: UUID | None,
    ) -> None:
        if config_id is None:
            return
        if self._llm_configs is None:
            self._llm_configs = build_llm_config_service(self._db)
        try:
            await self._llm_configs.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidLLMConfig, ProviderConfigNotFound) as error:
            raise AgentLLMConfigNotFoundError() from error

    async def _validate_instruction_template_reference(
        self,
        organization_id: UUID,
        template_id: UUID | None,
    ) -> None:
        if template_id is None:
            return
        from eylo.modules.templates.domain import (
            TemplateKind,
            TemplateNotFoundError,
        )
        from eylo.modules.templates.service import TemplateService

        try:
            template = await TemplateService(
                self.repository.db_session
            ).get(
                organization_id=organization_id,
                template_id=template_id,
            )
        except TemplateNotFoundError as error:
            raise InvalidAgentDefinitionError("Instruction template not found.") from error
        if template.kind != TemplateKind.AGENT_INSTRUCTIONS.value:
            raise InvalidAgentDefinitionError(
                "Agent definitions require an agent-instructions template."
            )

    async def _resolve_llm_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        if self._llm_configs is None:
            self._llm_configs = build_llm_config_service(self._db)
        try:
            resolved = await LLMConfigResolver(self._llm_configs).resolve_llm(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidLLMConfig, NotConfiguredError) as error:
            raise AgentLLMConfigNotFoundError(
                "Verify and enable the LLM config before publishing."
            ) from error
        return resolved.provider_config_revision

    async def _validate_email_config_reference(
        self,
        organization_id: UUID,
        config_id: UUID | None,
    ) -> None:
        if config_id is None:
            return
        service = self._email_config_service()
        try:
            await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidEmailConfig, ProviderConfigNotFound) as error:
            raise AgentEmailConfigError(
                "Email provider config was not found in this organization."
            ) from error

    async def _resolve_email_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        try:
            resolved = await EmailConfigResolver(
                self._email_config_service()
            ).resolve(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidEmailConfig, NotConfiguredError) as error:
            raise AgentEmailConfigError(
                "Verify and enable the email config before publishing."
            ) from error
        return resolved.provider_config_revision

    def _email_config_service(self) -> EmailConfigService:
        if self._email_configs is None:
            self._email_configs = build_email_config_service(self._db)
        return self._email_configs

    async def _validate_webrtc_config_reference(
        self,
        organization_id: UUID,
        config_id: UUID | None,
    ) -> None:
        if config_id is None:
            return
        service = self._webrtc_config_service()
        try:
            await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidWebRTCConfig, ProviderConfigNotFound) as error:
            raise AgentWebRTCConfigError(
                "WebRTC provider config was not found in this organization."
            ) from error

    async def _resolve_webrtc_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        try:
            resolved = await WebRTCConfigResolver(
                self._webrtc_config_service()
            ).resolve(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidWebRTCConfig, NotConfiguredError) as error:
            raise AgentWebRTCConfigError(
                "Verify and enable the WebRTC config before publishing."
            ) from error
        return resolved.provider_config_revision

    def _webrtc_config_service(self) -> WebRTCConfigService:
        if self._webrtc_configs is None:
            self._webrtc_configs = build_webrtc_config_service(self._db)
        return self._webrtc_configs

    async def _validate_reranking_config_reference(
        self,
        organization_id: UUID,
        config_id: UUID | None,
    ) -> None:
        if config_id is None:
            return
        service = self._reranking_config_service()
        try:
            await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidRerankingConfig, ProviderConfigNotFound) as error:
            raise AgentRerankingConfigError(
                "Reranking provider config was not found in this organization."
            ) from error

    async def _resolve_reranking_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        try:
            resolved = await RerankingConfigResolver(
                self._reranking_config_service()
            ).resolve(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidRerankingConfig, NotConfiguredError) as error:
            raise AgentRerankingConfigError(
                "Verify and enable the reranking config before publishing."
            ) from error
        return resolved.provider_config_revision

    def _reranking_config_service(self) -> RerankingConfigService:
        if self._reranking_configs is None:
            self._reranking_configs = build_reranking_config_service(self._db)
        return self._reranking_configs

    async def _validate_voice_config_reference(
        self,
        *,
        organization_id: UUID,
        agent_kind: AgentKind,
        config_id: UUID | None,
    ) -> int | None:
        if config_id is None:
            return None
        if agent_kind is AgentKind.BACKGROUND:
            raise AgentVoiceConfigError(
                "Background Agents cannot bind a Voice Config."
            )
        try:
            config = await VoiceConfigService(self._db).get(
                organization_id=organization_id,
                voice_config_id=config_id,
            )
        except VoiceConfigNotFound as error:
            raise AgentVoiceConfigError(
                "Voice Config was not found in this organization."
            ) from error
        return config.revision

    async def _validate_memory_config_reference(
        self,
        organization_id: UUID,
        config_id: UUID | None,
    ) -> None:
        if config_id is None:
            return
        service = self._memory_config_service()
        try:
            await service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidMemoryConfig, ProviderConfigNotFound) as error:
            raise AgentMemoryConfigError(
                "Memory provider config was not found in this organization."
            ) from error

    async def _resolve_memory_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        try:
            resolved = await MemoryConfigResolver(
                self._memory_config_service()
            ).resolve(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidMemoryConfig, NotConfiguredError) as error:
            raise AgentMemoryConfigError(
                "Verify and enable the memory config before publishing."
            ) from error
        return resolved.provider_config_revision

    def _memory_config_service(self) -> MemoryConfigService:
        if self._memory_configs is None:
            self._memory_configs = build_memory_config_service(self._db)
        return self._memory_configs

    async def _validate_file_upload_configuration(
        self,
        *,
        organization_id: UUID,
        allow_file_uploads: bool,
        config_id: UUID | None,
    ) -> None:
        if not allow_file_uploads:
            if config_id is not None:
                raise InvalidAgentDefinitionError(
                    "Clear the file upload embedding config when file uploads are disabled."
                )
            return
        if config_id is None:
            raise InvalidAgentDefinitionError(
                "Choose an embedding config when file uploads are enabled."
            )
        try:
            await self._embedding_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
        except (InvalidEmbeddingConfig, ProviderConfigNotFound) as error:
            raise AgentEmbeddingConfigError(
                "File upload embedding config was not found in this organization."
            ) from error

    async def _resolve_file_upload_embedding_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int:
        try:
            resolved = await EmbeddingConfigResolver(
                self._embedding_config_service()
            ).resolve(
                organization_id,
                provider_config_id=config_id,
            )
        except (InvalidEmbeddingConfig, NotConfiguredError) as error:
            raise AgentEmbeddingConfigError(
                "Verify and enable the file upload embedding config before publishing."
            ) from error
        return resolved.provider_config_revision

    def _embedding_config_service(self) -> EmbeddingConfigService:
        if self._embedding_configs is None:
            self._embedding_configs = build_embedding_config_service(self._db)
        return self._embedding_configs

    async def _has_memory_tools(
        self,
        agent_id: UUID,
        organization_id: UUID,
    ) -> bool:
        return await self._has_tools(
            agent_id,
            organization_id,
            _MEMORY_TOOL_NAMES,
        )

    async def _has_email_tools(
        self,
        agent_id: UUID,
        organization_id: UUID,
    ) -> bool:
        return await self._has_tools(
            agent_id,
            organization_id,
            _EMAIL_TOOL_NAMES,
        )

    async def _has_knowledge_tools(
        self,
        agent_id: UUID,
        organization_id: UUID,
    ) -> bool:
        tool_ids = {
            system_tool_id(name, organization_id) for name in _KNOWLEDGE_TOOL_NAMES
        }
        mappings = await AgentToolMappingRepository(
            db=self._db
        ).list_tools_by_agent_id(agent_id)
        return tool_ids.issubset({mapping.tool_id for mapping in mappings})

    async def _has_tools(
        self,
        agent_id: UUID,
        organization_id: UUID,
        names: tuple[str, ...],
    ) -> bool:
        tool_ids = {system_tool_id(name, organization_id) for name in names}
        mappings = await AgentToolMappingRepository(
            db=self._db
        ).list_tools_by_agent_id(agent_id)
        return any(mapping.tool_id in tool_ids for mapping in mappings)

    # get_by_slug
    async def get_by_slug(
        self, slug: str, organization_id: UUID
    ) -> Optional[AgentInDb]:
        agent = await self.repository.filter_one_(
            filters=[
                self.repository.model.slug == slug,
                self.repository.model.organization_id == organization_id,
            ]
        )
        return self.orm_to_schema(agent) if agent else None


class AgentToolService(EyloBaseService[AgentToolInDb]):
    """Agent Tool Service."""

    @property
    def schema(self) -> AgentToolInDb:
        """Schema for the "agents" domain."""
        return AgentToolInDb

    @property
    def repository(self) -> AgentToolMappingRepository:
        """Repository for the "agents" domain."""
        return self._repository

    @repository.setter
    def repository(self, value: AgentToolMappingRepository):
        """Repository for the "agents" domain."""
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize Agent Tool Service."""
        self._repository = AgentToolMappingRepository(db=db)
        self.tool_service = ToolService(db=db)

    async def create_(self, request: AgentToolCreate) -> AgentToolInDb:
        """Create Agent-Tool Mapping."""
        agent_tool = await self.repository.create_(
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            tool_revision=request.tool_revision,
            organization_id=request.organization_id,
        )
        return self.orm_to_schema(agent_tool)

    async def list_by_agent(self, agent_id: UUID) -> list[AgentToolInDb]:
        """List Tools by Agent."""
        tools = await self.repository.filter_(
            [self.repository.model.agent_id == agent_id]
        )
        return self.orm_to_schema_list(tools)

    async def get_by_tool_id_and_agent_id(
        self, tool_id: UUID, agent_id: UUID
    ) -> AgentToolInDb:
        await self.repository.filter_one_(
            filters=[
                self.repository.model.tool_id == tool_id,
                self.repository.model.agent_id == agent_id,
            ]
        )
        return self.orm_to_schema(tool_id)

    async def get_by_agent_and_tool(
        self, agent_id: UUID, tool_id: UUID
    ) -> Optional[AgentToolInDb]:
        """Get a single agent-tool mapping by agent and tool IDs."""
        mapping = await self.repository.filter_one_(
            filters=[
                self.repository.model.agent_id == agent_id,
                self.repository.model.tool_id == tool_id,
            ]
        )
        if mapping:
            return self.orm_to_schema(mapping)
        return None

    async def list_tools_for_agent(
        self, agent_id: UUID, organization_id: UUID
    ) -> list[ToolInDb]:
        """List all tools for a given agent."""
        mappings = await self.repository.list_tools_by_agent_id(agent_id=agent_id)
        refs = [(UUID(str(mapping.tool_id)), mapping.tool_revision) for mapping in mappings]
        if not refs:
            return []
        return await self.tool_service.list_exact(
            refs=refs,
            organization_id=organization_id,
        )

    async def remove_tool_from_agent(self, agent_id: UUID, tool_id: UUID) -> None:
        """Remove a tool from an agent."""
        await self.repository.delete_by_agent_and_tool_id(
            agent_id=agent_id, tool_id=tool_id
        )

    async def grant_curated_tool(
        self,
        *,
        agent_id: UUID,
        organization_id: UUID,
        curated_tool_id: UUID,
    ) -> None:
        """Grant one curated tool to an agent's draft.

        Curated grants carry no tool revision: a curated tool's definition is
        code, so there is nothing to pin. The grant reaches an agent run when
        the draft is published and copied into `agent_revision_tools`.
        """
        existing = await self.repository.filter_one_(
            filters=[
                self.repository.model.agent_id == agent_id,
                self.repository.model.curated_tool_id == curated_tool_id,
            ]
        )
        if existing is not None:
            if existing.deleted:
                existing.deleted = False
                await self.repository.save_(existing)
            return
        self.repository.db_session.add(
            AgentToolMappingModal(
                agent_id=agent_id,
                organization_id=organization_id,
                tool_id=None,
                tool_revision=None,
                curated_tool_id=curated_tool_id,
            )
        )
        await self.repository.db_session.flush()

    async def revoke_curated_tool(
        self,
        *,
        agent_id: UUID,
        curated_tool_id: UUID,
    ) -> bool:
        """Remove one curated grant from an agent's draft."""
        existing = await self.repository.filter_one_(
            filters=[
                self.repository.model.agent_id == agent_id,
                self.repository.model.curated_tool_id == curated_tool_id,
                self.repository.model.deleted.is_(False),
            ]
        )
        if existing is None:
            return False
        await self.repository.delete_(existing)
        return True

    async def list_curated_tool_ids(self, agent_id: UUID) -> list[UUID]:
        """Curated tool ids granted to an agent's draft."""
        rows = await self.repository.filter_all_(
            [
                self.repository.model.agent_id == agent_id,
                self.repository.model.curated_tool_id.is_not(None),
                self.repository.model.deleted.is_(False),
            ]
        )
        return [UUID(str(row.curated_tool_id)) for row in rows]

    async def list_by_agents(self, agent_ids: List[UUID]) -> List[AgentToolInDb]:
        tools = await self.repository.filter_all_(
            [self.repository.model.agent_id.in_(agent_ids)]
        )
        return self.orm_to_schema_list(tools)
