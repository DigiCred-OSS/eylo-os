"""Compose contact-owned chat authority with ordinary Knowledgebases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agents.services.revisions import AgentRevisionService
from eylo.modules.embedding_configs.domain import InvalidEmbeddingConfig
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.conversation.widget_authority import (
    resolve_widget_conversation_authority,
)
from eylo.pipelines.embedding.resolver import resolve_pinned_embedding_runtime


class ConversationFileUploadsNotAllowed(KnowledgebaseError):
    """The exact Agent revision does not permit end-user file uploads."""


@dataclass(frozen=True, slots=True)
class ConversationFileUploadAuthority:
    organization_id: UUID
    conversation_id: UUID
    agent_id: UUID
    agent_revision: int
    embedding_provider_config_id: UUID
    embedding_provider_config_revision: int


async def resolve_conversation_file_upload_authority(
    *,
    organization_id: UUID,
    contact_id: UUID,
    conversation_id: UUID,
    session: AsyncSession,
) -> ConversationFileUploadAuthority:
    conversation = await resolve_widget_conversation_authority(
        organization_id=organization_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        session=session,
    )
    revision = await AgentRevisionService(session).get_revision(
        organization_id=organization_id,
        agent_id=conversation.agent_id,
        revision=conversation.agent_revision,
    )
    config_id = revision.file_upload_embedding_provider_config_id
    config_revision = revision.file_upload_embedding_provider_config_revision
    if not revision.allow_file_uploads or config_id is None or config_revision is None:
        raise ConversationFileUploadsNotAllowed()
    return ConversationFileUploadAuthority(
        organization_id=organization_id,
        conversation_id=conversation_id,
        agent_id=conversation.agent_id,
        agent_revision=conversation.agent_revision,
        embedding_provider_config_id=config_id,
        embedding_provider_config_revision=config_revision,
    )


async def ensure_conversation_file_knowledgebase(
    authority: ConversationFileUploadAuthority,
    *,
    session: AsyncSession,
):
    try:
        runtime = await resolve_pinned_embedding_runtime(
            authority.organization_id,
            provider_config_id=authority.embedding_provider_config_id,
            provider_config_revision=authority.embedding_provider_config_revision,
            db=session,
        )
    except (InvalidEmbeddingConfig, NotConfiguredError):
        raise KnowledgebaseError(
            "The pinned file upload embedding config is unavailable."
        ) from None
    return await KnowledgebaseService(session).ensure_conversation_knowledgebase(
        organization_id=authority.organization_id,
        conversation_id=authority.conversation_id,
        agent_id=authority.agent_id,
        embedding_space=runtime.space,
    )


__all__ = [
    "ConversationFileUploadAuthority",
    "ConversationFileUploadsNotAllowed",
    "ensure_conversation_file_knowledgebase",
    "resolve_conversation_file_upload_authority",
]
