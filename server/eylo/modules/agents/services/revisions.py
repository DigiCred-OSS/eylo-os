"""Publication authority for immutable executable agent revisions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.revisions import (
    DefinitionHeaderState,
    DefinitionLifecycle,
    PublishedRevisionState,
    RevisionAvailability,
)
from eylo.modules.agents.domain import InvalidAgentDefinitionError
from eylo.modules.agents.models import (
    AgentBackgroundAgentModel,
    AgentKind,
    AgentRevisionBackgroundAgentModel,
    AgentRevisionModel,
    AgentRevisionToolModel,
    AgentStatus,
    AgentToolMappingModal,
    AgentsModel,
)
from eylo.modules.templates.domain import TemplateKind
from eylo.modules.templates.service import TemplateService
from eylo.modules.tools.services.indb import ToolService


class AgentRevisionService:
    """Validate a complete draft, publish it, and load exact revisions."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()

    async def publish(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
        actor_id: UUID | None = None,
    ) -> AgentRevisionModel:
        header = await self._get_header(
            organization_id,
            agent_id,
            for_update=True,
        )
        next_revision = (header.published_revision or 0) + 1
        next_state = _header_state(header).publish(
            revision=next_revision,
            expected_draft_version=expected_draft_version,
        )

        template_id, template_revision = await self._resolve_template(header)
        provider_refs = await self._resolve_provider_refs(header)
        voice_publication = await self._resolve_voice_config(header)
        voice_config = (
            None
            if voice_publication is None
            else voice_publication.config.model_dump(mode="json")
        )
        tool_refs = await self._tool_refs(header)
        curated_tool_ids = await self._curated_tool_refs(header)
        background_refs = await self._background_refs(header)

        published_at = datetime.now(timezone.utc)
        revision = AgentRevisionModel(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=next_revision,
            name=header.name,
            slug=header.slug,
            description=header.description,
            webhook=header.webhook,
            kind=_enum_value(header.kind),
            implementation=header.implementation,
            voice_config_id=(
                None
                if voice_publication is None
                else voice_publication.voice_config_id
            ),
            voice_config_revision=(
                None
                if voice_publication is None
                else voice_publication.voice_config_revision
            ),
            instruction_template_id=template_id,
            instruction_template_revision=template_revision,
            llm_provider_config_id=provider_refs["llm"][0],
            llm_provider_config_revision=provider_refs["llm"][1],
            email_provider_config_id=provider_refs["email"][0],
            email_provider_config_revision=provider_refs["email"][1],
            webrtc_provider_config_id=provider_refs["webrtc"][0],
            webrtc_provider_config_revision=provider_refs["webrtc"][1],
            reranking_provider_config_id=provider_refs["reranking"][0],
            reranking_provider_config_revision=provider_refs["reranking"][1],
            memory_provider_config_id=provider_refs["memory"][0],
            memory_provider_config_revision=provider_refs["memory"][1],
            allow_file_uploads=header.allow_file_uploads,
            file_upload_embedding_provider_config_id=provider_refs[
                "file_upload_embedding"
            ][0],
            file_upload_embedding_provider_config_revision=provider_refs[
                "file_upload_embedding"
            ][1],
            stt_provider_config_id=_voice_ref(voice_config, "stt")[0],
            stt_provider_config_revision=_voice_ref(voice_config, "stt")[1],
            tts_provider_config_id=_voice_ref(voice_config, "tts")[0],
            tts_provider_config_revision=_voice_ref(voice_config, "tts")[1],
            realtime_provider_config_id=_voice_ref(voice_config, "realtime")[0],
            realtime_provider_config_revision=_voice_ref(
                voice_config,
                "realtime",
            )[1],
            storage_provider_config_id=_voice_ref(voice_config, "storage")[0],
            storage_provider_config_revision=_voice_ref(voice_config, "storage")[1],
            llm_overrides=dict(header.llm_overrides or {}),
            voice_config=voice_config,
            published_at=published_at,
            published_by=actor_id,
        )
        self._db.add(revision)
        await self._db.flush()

        self._db.add_all(
            [
                AgentRevisionToolModel(
                    agent_id=agent_id,
                    agent_revision=next_revision,
                    tool_id=tool_id,
                    tool_revision=tool_revision,
                    organization_id=organization_id,
                )
                for tool_id, tool_revision in tool_refs
            ]
        )
        # Curated grants carry no tool revision: their definition is code, so
        # there is nothing to pin into the revision beyond the binding itself.
        self._db.add_all(
            [
                AgentRevisionToolModel(
                    agent_id=agent_id,
                    agent_revision=next_revision,
                    tool_id=None,
                    tool_revision=None,
                    curated_tool_id=curated_tool_id,
                    organization_id=organization_id,
                )
                for curated_tool_id in curated_tool_ids
            ]
        )
        self._db.add_all(
            [
                AgentRevisionBackgroundAgentModel(
                    agent_id=agent_id,
                    agent_revision=next_revision,
                    background_agent_id=background_agent_id,
                    background_agent_revision=background_revision,
                    organization_id=organization_id,
                )
                for background_agent_id, background_revision in background_refs
            ]
        )
        await self._db.flush()

        for kind, (config_id, config_revision) in provider_refs.items():
            setattr(header, f"{kind}_provider_config_id", config_id)
            setattr(header, f"{kind}_provider_config_revision", config_revision)
        _apply_header_state(header, next_state)
        header.status = AgentStatus.ACTIVE
        await self._db.flush()
        return revision

    async def withdraw(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
    ) -> AgentsModel:
        header = await self._get_header(
            organization_id,
            agent_id,
            for_update=True,
        )
        _apply_header_state(header, _header_state(header).withdraw())
        header.status = AgentStatus.INACTIVE
        await self._db.flush()
        return header

    async def mark_draft_changed(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        expected_draft_version: int,
    ) -> AgentsModel:
        """Advance optimistic draft state after a related aggregate changes."""
        header = await self._get_header(
            organization_id,
            agent_id,
            for_update=True,
        )
        _apply_header_state(
            header,
            _header_state(header).edit(
                expected_draft_version=expected_draft_version
            ),
        )
        await self._db.flush()
        return header

    async def revoke(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> AgentRevisionModel:
        header = await self._get_header(
            organization_id,
            agent_id,
            for_update=True,
        )
        row = await self.get_revision(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
            for_update=True,
        )
        revoked = _revision_state(row).revoke(
            actor_id=actor_id,
            reason=reason,
            at=datetime.now(timezone.utc),
        )
        row.availability = revoked.availability.value
        row.revoked_at = revoked.revoked_at
        row.revoked_by = revoked.revoked_by
        row.revocation_reason = revoked.revocation_reason
        row.cancellation_requested_at = revoked.cancellation_requested_at
        if header.published_revision == revision:
            _apply_header_state(header, _header_state(header).withdraw())
            header.status = AgentStatus.INACTIVE
        await self._db.flush()
        return row

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        for_update: bool = False,
    ) -> AgentRevisionModel:
        header = await self._get_header(
            organization_id,
            agent_id,
            for_update=for_update,
        )
        revision = _header_state(header).revision_for_new_work()
        return await self.get_revision(
            organization_id=organization_id,
            agent_id=agent_id,
            revision=revision,
            for_update=for_update,
        )

    async def list_available_for_widget(
        self,
        *,
        organization_id: UUID,
        agent_ids: Sequence[UUID] | None = None,
    ) -> list[AgentRevisionModel]:
        """List immutable revisions that may start a widget conversation."""
        query = (
            select(AgentRevisionModel)
            .join(
                AgentsModel,
                and_(
                    AgentsModel.id == AgentRevisionModel.agent_id,
                    AgentsModel.organization_id
                    == AgentRevisionModel.organization_id,
                    AgentsModel.published_revision == AgentRevisionModel.revision,
                ),
            )
            .where(
                AgentRevisionModel.organization_id == organization_id,
                AgentRevisionModel.kind == AgentKind.CONVERSATIONAL.value,
                AgentRevisionModel.availability
                == RevisionAvailability.PUBLISHED.value,
                AgentRevisionModel.deleted.is_(False),
                AgentsModel.status == AgentStatus.ACTIVE,
                AgentsModel.deleted.is_(False),
            )
            .order_by(
                AgentRevisionModel.name.asc(),
                AgentRevisionModel.agent_id.asc(),
            )
        )
        if agent_ids is not None:
            query = query.where(AgentRevisionModel.agent_id.in_(agent_ids))
        rows = await self._db.scalars(query)
        return list(rows.all())

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
        for_update: bool = False,
    ) -> AgentRevisionModel:
        query = select(AgentRevisionModel).where(
            AgentRevisionModel.organization_id == organization_id,
            AgentRevisionModel.agent_id == agent_id,
            AgentRevisionModel.revision == revision,
            AgentRevisionModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self._db.scalar(query)
        if row is None:
            from eylo.modules.agents.exceptions import AgentNotFoundError

            raise AgentNotFoundError("Agent revision not found.")
        _revision_state(row).require_available()
        return row

    async def list_tool_refs(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
    ) -> list[tuple[UUID, int]]:
        rows = await self._db.scalars(
            select(AgentRevisionToolModel).where(
                AgentRevisionToolModel.organization_id == organization_id,
                AgentRevisionToolModel.agent_id == agent_id,
                AgentRevisionToolModel.agent_revision == revision,
                AgentRevisionToolModel.tool_id.is_not(None),
                AgentRevisionToolModel.deleted.is_(False),
            )
        )
        return [(row.tool_id, row.tool_revision) for row in rows.all()]

    async def list_curated_tool_ids(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
    ) -> list[UUID]:
        """Curated tool grants pinned into one exact agent revision.

        Returned as bare ids rather than (id, revision) pairs: a curated tool's
        definition is code and has no revision to pin.
        """
        rows = await self._db.scalars(
            select(AgentRevisionToolModel).where(
                AgentRevisionToolModel.organization_id == organization_id,
                AgentRevisionToolModel.agent_id == agent_id,
                AgentRevisionToolModel.agent_revision == revision,
                AgentRevisionToolModel.curated_tool_id.is_not(None),
                AgentRevisionToolModel.deleted.is_(False),
            )
        )
        return [row.curated_tool_id for row in rows.all()]

    async def list_background_refs(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
    ) -> list[tuple[UUID, int]]:
        rows = await self._db.scalars(
            select(AgentRevisionBackgroundAgentModel).where(
                AgentRevisionBackgroundAgentModel.organization_id
                == organization_id,
                AgentRevisionBackgroundAgentModel.agent_id == agent_id,
                AgentRevisionBackgroundAgentModel.agent_revision == revision,
                AgentRevisionBackgroundAgentModel.deleted.is_(False),
            )
        )
        return [
            (row.background_agent_id, row.background_agent_revision)
            for row in rows.all()
        ]

    async def _get_header(
        self,
        organization_id: UUID,
        agent_id: UUID,
        *,
        for_update: bool = False,
    ) -> AgentsModel:
        query = select(AgentsModel).where(
            AgentsModel.organization_id == organization_id,
            AgentsModel.id == agent_id,
            AgentsModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        header = await self._db.scalar(query)
        if header is None:
            from eylo.modules.agents.exceptions import AgentNotFoundError

            raise AgentNotFoundError()
        return header

    async def _resolve_template(
        self,
        header: AgentsModel,
    ) -> tuple[UUID | None, int | None]:
        code_owned = (
            _enum_value(header.kind) == AgentKind.BACKGROUND.value
            and header.implementation is not None
        )
        if code_owned:
            if header.instruction_template_id is not None:
                raise InvalidAgentDefinitionError(
                    "Code-owned background agents cannot bind an instruction template."
                )
            return None, None
        if header.instruction_template_id is None:
            raise InvalidAgentDefinitionError(
                "Assign a published agent-instructions template before publishing."
            )
        template = await TemplateService(self._db).resolve_for_new_work(
            organization_id=header.organization_id,
            template_id=header.instruction_template_id,
        )
        if template.kind != TemplateKind.AGENT_INSTRUCTIONS.value:
            raise InvalidAgentDefinitionError(
                "Agent definitions require an agent-instructions template."
            )
        if template.variable_schema != {"variables": []}:
            raise InvalidAgentDefinitionError(
                "Agent instruction templates cannot declare runtime variables in V1."
            )
        return template.template_id, template.revision

    async def _resolve_provider_refs(
        self,
        header: AgentsModel,
    ) -> dict[str, tuple[UUID | None, int | None]]:
        from eylo.modules.agents.services.indb import AgentService

        service = AgentService(self._db)
        if header.llm_provider_config_id is None:
            raise InvalidAgentDefinitionError(
                "Assign a ready LLM config before publishing the agent."
            )
        refs: dict[str, tuple[UUID | None, int | None]] = {
            "llm": (
                header.llm_provider_config_id,
                await service._resolve_llm_revision(
                    header.organization_id,
                    header.llm_provider_config_id,
                ),
            )
        }
        optional_resolvers = {
            "email": service._resolve_email_revision,
            "webrtc": service._resolve_webrtc_revision,
            "reranking": service._resolve_reranking_revision,
            "memory": service._resolve_memory_revision,
            "file_upload_embedding": (
                service._resolve_file_upload_embedding_revision
            ),
        }
        for kind, resolver in optional_resolvers.items():
            config_id = getattr(header, f"{kind}_provider_config_id")
            refs[kind] = (
                (None, None)
                if config_id is None
                else (
                    config_id,
                    await resolver(header.organization_id, config_id),
                )
            )
        if refs["email"][0] is None and await service._has_email_tools(
            header.id,
            header.organization_id,
        ):
            raise InvalidAgentDefinitionError(
                "Assign a ready email config before publishing an agent "
                "with the send_email tool."
            )
        if refs["memory"][0] is None and await service._has_memory_tools(
            header.id,
            header.organization_id,
        ):
            raise InvalidAgentDefinitionError(
                "Assign a ready memory config before publishing an agent "
                "with memory tools."
            )
        if header.allow_file_uploads and not await service._has_knowledge_tools(
            header.id,
            header.organization_id,
        ):
            raise InvalidAgentDefinitionError(
                "Assign kb_query, kb_write_destinations, and kb_write before "
                "publishing an agent with file uploads."
            )
        return refs

    async def _resolve_voice_config(self, header: AgentsModel):
        from eylo.modules.agents.exceptions import AgentVoiceConfigError
        from eylo.modules.voice.exceptions import (
            VoiceConfigConflict,
            VoiceConfigNotFound,
        )
        from eylo.modules.voice.services.voice_configs import VoiceConfigService

        if header.voice_config_id is None:
            if header.voice_config_revision is not None:
                raise AgentVoiceConfigError(
                    "Agent Voice Config binding is incomplete."
                )
            return None
        if header.voice_config_revision is None:
            raise AgentVoiceConfigError("Agent Voice Config binding is incomplete.")
        if _enum_value(header.kind) == AgentKind.BACKGROUND.value:
            raise AgentVoiceConfigError(
                "Background Agents cannot publish with a Voice Config."
            )
        try:
            return await VoiceConfigService(self._db).resolve_for_publish(
                organization_id=header.organization_id,
                voice_config_id=header.voice_config_id,
                expected_revision=header.voice_config_revision,
            )
        except (VoiceConfigNotFound, VoiceConfigConflict, ValueError) as error:
            raise AgentVoiceConfigError(str(error)) from error

    async def _tool_refs(self, header: AgentsModel) -> list[tuple[UUID, int]]:
        rows = await self._db.scalars(
            select(AgentToolMappingModal).where(
                AgentToolMappingModal.agent_id == header.id,
                AgentToolMappingModal.organization_id == header.organization_id,
                AgentToolMappingModal.tool_id.is_not(None),
                AgentToolMappingModal.deleted.is_(False),
            )
        )
        refs = [(row.tool_id, row.tool_revision) for row in rows.all()]
        if refs:
            tools = await ToolService(self._db).list_exact(
                refs=refs,
                organization_id=header.organization_id,
            )
            if len(tools) != len(refs):
                raise InvalidAgentDefinitionError(
                    "Every agent tool grant must resolve to an exact available revision."
                )
            model_names = [tool.llm_config.name for tool in tools]
            if any(not name.strip() for name in model_names):
                raise InvalidAgentDefinitionError(
                    "Every tool in one agent revision requires a non-empty "
                    "model-visible name."
                )
            if len(model_names) != len(set(model_names)):
                raise InvalidAgentDefinitionError(
                    "Every tool in one agent revision requires a unique "
                    "model-visible name."
                )
        return refs

    async def _curated_tool_refs(self, header: AgentsModel) -> list[UUID]:
        """Curated tool grants on the draft, to copy into the new revision."""
        rows = await self._db.scalars(
            select(AgentToolMappingModal).where(
                AgentToolMappingModal.agent_id == header.id,
                AgentToolMappingModal.organization_id == header.organization_id,
                AgentToolMappingModal.curated_tool_id.is_not(None),
                AgentToolMappingModal.deleted.is_(False),
            )
        )
        return [UUID(str(row.curated_tool_id)) for row in rows.all()]

    async def _background_refs(
        self,
        header: AgentsModel,
    ) -> list[tuple[UUID, int]]:
        rows = await self._db.scalars(
            select(AgentBackgroundAgentModel).where(
                AgentBackgroundAgentModel.agent_id == header.id,
                AgentBackgroundAgentModel.enabled.is_(True),
                AgentBackgroundAgentModel.deleted.is_(False),
            )
        )
        refs: list[tuple[UUID, int]] = []
        for attachment in rows.all():
            target = await self._get_header(
                header.organization_id,
                attachment.background_agent_id,
            )
            if _enum_value(target.kind) != AgentKind.BACKGROUND.value:
                raise InvalidAgentDefinitionError(
                    "Enabled background attachments must reference background agents."
                )
            target_revision = _header_state(target).revision_for_new_work()
            await self.get_revision(
                organization_id=header.organization_id,
                agent_id=target.id,
                revision=target_revision,
            )
            refs.append((target.id, target_revision))
        return refs


def _header_state(row: AgentsModel) -> DefinitionHeaderState:
    return DefinitionHeaderState(
        lifecycle=DefinitionLifecycle(row.lifecycle),
        published_revision=row.published_revision,
        draft_version=row.draft_version,
        draft_dirty=row.draft_dirty,
    )


def _apply_header_state(row: AgentsModel, state: DefinitionHeaderState) -> None:
    row.lifecycle = state.lifecycle.value
    row.published_revision = state.published_revision
    row.draft_version = state.draft_version
    row.draft_dirty = state.draft_dirty


def _revision_state(row: AgentRevisionModel) -> PublishedRevisionState:
    return PublishedRevisionState(
        published_at=row.published_at,
        availability=row.availability,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
        cancellation_requested_at=row.cancellation_requested_at,
    )


def _voice_ref(
    config: dict | None,
    kind: str,
) -> tuple[UUID | None, int | None]:
    if config is None:
        return None, None
    raw_id = config.get(f"{kind}_provider_config_id")
    raw_revision = config.get(f"{kind}_provider_config_revision")
    # Common Voice Configs may retain selections that are inactive in the
    # chosen runtime mode. Publication marks active refs by resolving a
    # revision; only those exact pairs belong in the immutable Agent row.
    if raw_revision is None:
        return None, None
    if raw_id is None:
        raise InvalidAgentDefinitionError(
            f"Published {kind} voice provider revision has no config ID."
        )
    return (
        UUID(str(raw_id)),
        int(raw_revision),
    )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


__all__ = ["AgentRevisionService"]
