"""Knowledgebase definitions and agent grants.

Two responsibilities, and the second is the interesting one. Creating a KB is
ordinary CRUD; granting one to an agent is the platform deciding what an agent
may read and change, so every path here that could widen access does so
explicitly or not at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import DurableState
from eylo.common.contracts.embedding import EmbeddingSpace
from eylo.common.contracts.knowledgebase import KnowledgeAccess, KnowledgeScope
from eylo.common.models import slugify_column
from eylo.events.schema.py_events.knowledgebase import (
    KnowledgebaseAccessTransition,
    KnowledgebaseChangedField,
    KnowledgebaseTransition,
)
from eylo.modules.agents.models import AgentsModel
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.knowledgebase.events import (
    register_knowledgebase_access_changed,
    register_knowledgebase_lifecycle,
)
from eylo.modules.knowledgebase.jobs import (
    TERMINAL_STATES,
    KnowledgeCorpusImportModel,
    KnowledgeIngestionJobModel,
    KnowledgeReindexJobModel,
)
from eylo.modules.knowledgebase.models import (
    KnowledgeChunkModel,
    KnowledgebaseGrantModel,
    KnowledgebaseModel,
)
from eylo.modules.knowledgebase.vendors import (
    KnowledgebaseMetadata,
    configuration_problem,
    needs_embeddings,
    normalize_metadata,
)

logger = logging.getLogger(__name__)


class KnowledgebaseError(Exception):
    """An operator asked for a knowledgebase arrangement that cannot exist."""


class KnowledgebaseNotFound(KnowledgebaseError):
    """An organization-owned knowledgebase resource was not found."""


@dataclass(frozen=True, slots=True)
class KnowledgebaseDeletion:
    """Committed product deletion plus engine tasks that need notification."""

    task_ids: tuple[UUID, ...]


class KnowledgebaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- definitions -------------------------------------------------

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        vendor: str,
        scope: KnowledgeScope,
        scope_id: str,
        writable: bool = False,
        metadata: KnowledgebaseMetadata | dict | None = None,
        embedding_space: EmbeddingSpace | None = None,
    ) -> KnowledgebaseModel:
        """Define a knowledgebase.

        An ORGANIZATION-scoped KB must point at the organization creating it.
        Without that check, `scope_id` — which is not a foreign key, because it
        addresses three different tables — would be a free-text field through
        which one organization could name another's id and read its knowledge.
        """
        # Checked here, where the operator can still fix it. Without this the
        # knowledgebase is created, granted, and then skipped on every query by
        # the very code that exists to stop one broken vendor blinding an
        # agent — so the failure is permanent, silent, and looks like an empty
        # knowledgebase rather than a misconfigured one.
        problem = configuration_problem(vendor, metadata)
        if problem:
            raise KnowledgebaseError(problem)

        if needs_embeddings(vendor) and embedding_space is None:
            raise KnowledgebaseError(
                f"The '{vendor}' vendor requires embedding_provider_config_id. "
                "Select a ready config from /api/embedding-configs."
            )
        if not needs_embeddings(vendor) and embedding_space is not None:
            raise KnowledgebaseError(
                f"The '{vendor}' vendor does not use an embedding config."
            )
        if (
            embedding_space is not None
            and str(embedding_space.organization_id) != str(organization_id)
        ):
            raise KnowledgebaseError(
                "Embedding config must belong to the knowledgebase organization."
            )

        normalized_scope_id = await self._require_scope_owner(
            scope,
            scope_id,
            organization_id,
        )

        knowledgebase = KnowledgebaseModel(
            organization_id=organization_id,
            name=name,
            slug=slugify_column(name),
            vendor=vendor,
            scope=scope,
            scope_id=normalized_scope_id,
            writable=writable,
            meta=normalize_metadata(metadata),
            embedding_provider_config_id=(
                embedding_space.provider_config_id if embedding_space else None
            ),
            embedding_provider_config_revision=(
                embedding_space.provider_config_revision if embedding_space else None
            ),
            embedding_provider=(embedding_space.provider if embedding_space else None),
            embedding_endpoint=(embedding_space.endpoint if embedding_space else None),
            embedding_model=(embedding_space.model if embedding_space else None),
            embedding_dimensions=(
                embedding_space.dimensions if embedding_space else None
            ),
            embedding_semantic_options=(
                dict(embedding_space.semantic_options) if embedding_space else None
            ),
            embedding_space_id=(embedding_space.id if embedding_space else None),
        )
        self.session.add(knowledgebase)
        await self.session.flush()
        register_knowledgebase_lifecycle(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase.id,
            transition=KnowledgebaseTransition.CREATED,
        )
        return knowledgebase

    async def list_for_organization(
        self, organization_id: UUID
    ) -> list[KnowledgebaseModel]:
        result = await self.session.execute(
            select(KnowledgebaseModel).where(
                KnowledgebaseModel.organization_id == organization_id,
                KnowledgebaseModel.deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    async def find_conversation_knowledgebase(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> KnowledgebaseModel | None:
        """Return the one live KB owned by an exact conversation, if created."""
        return await self.session.scalar(
            select(KnowledgebaseModel).where(
                KnowledgebaseModel.organization_id == organization_id,
                KnowledgebaseModel.scope == KnowledgeScope.CONVERSATION,
                KnowledgebaseModel.scope_id == str(conversation_id),
                KnowledgebaseModel.deleted.is_(False),
            )
        )

    async def ensure_conversation_knowledgebase(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        agent_id: UUID,
        embedding_space: EmbeddingSpace,
    ) -> KnowledgebaseModel:
        """Create once, then grant the Agent ordinary read-write access."""
        normalized_conversation_id = await self._require_scope_owner(
            KnowledgeScope.CONVERSATION,
            str(conversation_id),
            organization_id,
            for_update=True,
        )
        knowledgebase = await self.find_conversation_knowledgebase(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        if knowledgebase is None:
            knowledgebase = await self.create(
                organization_id=organization_id,
                name="Conversation files",
                vendor="pgvector",
                scope=KnowledgeScope.CONVERSATION,
                scope_id=normalized_conversation_id,
                writable=True,
                embedding_space=embedding_space,
            )
        elif (
            knowledgebase.vendor != "pgvector"
            or not knowledgebase.writable
            or knowledgebase.embedding_space_id != embedding_space.id
        ):
            raise KnowledgebaseError(
                "The conversation already has an incompatible knowledgebase."
            )

        await self.grant(
            organization_id=organization_id,
            agent_id=agent_id,
            knowledgebase_id=knowledgebase.id,
            access=KnowledgeAccess.READ_WRITE,
        )
        return knowledgebase

    async def get(
        self,
        knowledgebase_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
        for_share: bool = False,
    ) -> KnowledgebaseModel:
        if for_update and for_share:
            raise ValueError("A knowledgebase cannot take two lock modes.")
        query = select(KnowledgebaseModel).where(
            KnowledgebaseModel.id == knowledgebase_id,
            # Always filtered by organization, never fetched then checked.
            # A fetch-then-check leaks existence through timing and through
            # whichever error the check forgets to raise.
            KnowledgebaseModel.organization_id == organization_id,
            KnowledgebaseModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        elif for_share:
            query = query.with_for_update(read=True)
        result = await self.session.execute(query)
        knowledgebase = result.scalar_one_or_none()
        if knowledgebase is None:
            raise KnowledgebaseNotFound("Knowledgebase not found.")
        return knowledgebase

    async def update(
        self,
        knowledgebase_id: UUID,
        organization_id: UUID,
        *,
        name: str | None = None,
        writable: bool | None = None,
        metadata: KnowledgebaseMetadata | dict | None = None,
    ) -> KnowledgebaseModel:
        knowledgebase = await self.get(knowledgebase_id, organization_id)
        changed_fields: list[KnowledgebaseChangedField] = []
        if name is not None and name != knowledgebase.name:
            knowledgebase.name = name
            knowledgebase.slug = slugify_column(name)
            changed_fields.append(KnowledgebaseChangedField.NAME)
        if writable is not None and writable != knowledgebase.writable:
            # Revoking write leaves READ_WRITE grants in place, and they stop
            # working immediately because `assert_writable` checks the KB as
            # well as the grant. Rewriting the grants instead would silently
            # lose an operator's intent if write were turned back on.
            knowledgebase.writable = writable
            changed_fields.append(KnowledgebaseChangedField.WRITABLE)
        if metadata is not None:
            # Re-validated: replacing metadata can remove the key the vendor
            # needs, and an update that silently breaks a working knowledgebase
            # is worse than one that is refused.
            problem = configuration_problem(knowledgebase.vendor, metadata)
            if problem:
                raise KnowledgebaseError(problem)
            normalized_metadata = normalize_metadata(metadata)
            if normalized_metadata != knowledgebase.meta:
                knowledgebase.meta = normalized_metadata
                changed_fields.append(KnowledgebaseChangedField.METADATA)
        await self.session.flush()
        if changed_fields:
            register_knowledgebase_lifecycle(
                organization_id=organization_id,
                knowledgebase_id=knowledgebase_id,
                transition=KnowledgebaseTransition.UPDATED,
                changed_fields=changed_fields,
            )
        return knowledgebase

    async def delete(
        self,
        knowledgebase_id: UUID,
        organization_id: UUID,
    ) -> KnowledgebaseDeletion:
        """Retire the aggregate while holding the lock every writer respects."""
        knowledgebase = await self.get(
            knowledgebase_id,
            organization_id,
            for_update=True,
        )

        jobs = list(
            (
                await self.session.scalars(
                    select(KnowledgeIngestionJobModel)
                    .where(
                        KnowledgeIngestionJobModel.knowledgebase_id
                        == knowledgebase_id,
                        KnowledgeIngestionJobModel.organization_id == organization_id,
                        KnowledgeIngestionJobModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        imports = list(
            (
                await self.session.scalars(
                    select(KnowledgeCorpusImportModel)
                    .where(
                        KnowledgeCorpusImportModel.knowledgebase_id
                        == knowledgebase_id,
                        KnowledgeCorpusImportModel.organization_id == organization_id,
                        KnowledgeCorpusImportModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        reindexes = list(
            (
                await self.session.scalars(
                    select(KnowledgeReindexJobModel)
                    .where(
                        KnowledgeReindexJobModel.knowledgebase_id
                        == knowledgebase_id,
                        KnowledgeReindexJobModel.organization_id == organization_id,
                        KnowledgeReindexJobModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        finished_at = datetime.now(timezone.utc)
        task_ids: set[UUID] = set()
        for work in [*jobs, *imports, *reindexes]:
            if work.absurd_task_id is not None:
                task_ids.add(work.absurd_task_id)
            if work.state not in TERMINAL_STATES:
                work.state = DurableState.CANCELLED
                work.finished_at = finished_at
            work.deleted = True

        deleted_chunks = await self.session.execute(
            delete(KnowledgeChunkModel).where(
                KnowledgeChunkModel.knowledgebase_id == knowledgebase_id,
                KnowledgeChunkModel.organization_id == organization_id,
            )
        )
        revoked_grants = await self.session.execute(
            delete(KnowledgebaseGrantModel).where(
                KnowledgebaseGrantModel.knowledgebase_id == knowledgebase_id,
                KnowledgebaseGrantModel.organization_id == organization_id,
            )
        )
        knowledgebase.deleted = True
        await self.session.flush()
        register_knowledgebase_lifecycle(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            transition=KnowledgebaseTransition.DELETED,
            affected_ingestion_jobs=len(jobs),
            affected_corpus_imports=len(imports),
            affected_reindex_jobs=len(reindexes),
            deleted_chunks=int(deleted_chunks.rowcount or 0),
            revoked_grants=int(revoked_grants.rowcount or 0),
        )
        return KnowledgebaseDeletion(task_ids=tuple(sorted(task_ids, key=str)))

    # ---- grants ------------------------------------------------------

    async def grant(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        knowledgebase_id: UUID,
        access: KnowledgeAccess = KnowledgeAccess.READ,
    ) -> KnowledgebaseGrantModel:
        """Give an agent access to a knowledgebase.

        Both sides are loaded through the organization and the row carries the
        same organization in composite foreign keys. A forgotten caller check
        therefore cannot make a cross-organization grant persist.
        """
        knowledgebase = await self.get(knowledgebase_id, organization_id)
        await self._require_agent(agent_id, organization_id)

        if access is KnowledgeAccess.READ_WRITE and not knowledgebase.writable:
            raise KnowledgebaseError(
                f"Knowledgebase '{knowledgebase.name}' does not accept writes, "
                "so it cannot be granted READ_WRITE."
            )

        existing = await self._find_grant(
            organization_id,
            agent_id,
            knowledgebase_id,
        )
        if existing is not None:
            # Regranting is how an operator changes the mode. Silently keeping
            # the old one would leave them believing they had upgraded it.
            if existing.access == access:
                return existing
            existing.access = access
            await self.session.flush()
            register_knowledgebase_access_changed(
                organization_id=organization_id,
                knowledgebase_id=knowledgebase_id,
                agent_id=agent_id,
                transition=KnowledgebaseAccessTransition.CHANGED,
                access=access,
            )
            return existing

        grant = KnowledgebaseGrantModel(
            organization_id=organization_id,
            agent_id=agent_id,
            knowledgebase_id=knowledgebase_id,
            access=access,
        )
        self.session.add(grant)
        await self.session.flush()
        register_knowledgebase_access_changed(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            agent_id=agent_id,
            transition=KnowledgebaseAccessTransition.GRANTED,
            access=access,
        )
        return grant

    async def revoke(
        self, *, organization_id: UUID, agent_id: UUID, knowledgebase_id: UUID
    ) -> None:
        await self.get(knowledgebase_id, organization_id)
        grant = await self._find_grant(
            organization_id,
            agent_id,
            knowledgebase_id,
        )
        if grant is None:
            raise KnowledgebaseError("This agent has no grant for that knowledgebase.")
        await self.session.delete(grant)
        await self.session.flush()
        register_knowledgebase_access_changed(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            agent_id=agent_id,
            transition=KnowledgebaseAccessTransition.REVOKED,
            access=None,
        )

    async def grants_for_agent(
        self,
        agent_id: UUID,
        organization_id: UUID,
    ) -> list[KnowledgebaseGrantModel]:
        """Every live grant an agent holds, with its knowledgebase loaded.

        Filters deleted knowledgebases here rather than leaving it to callers:
        the tools resolve scopes from this list, and a deleted KB that stayed in
        it would keep answering queries.
        """
        await self._require_agent(agent_id, organization_id)
        result = await self.session.execute(
            select(KnowledgebaseGrantModel)
            .join(
                KnowledgebaseModel,
                KnowledgebaseModel.id == KnowledgebaseGrantModel.knowledgebase_id,
            )
            .where(
                KnowledgebaseGrantModel.agent_id == agent_id,
                KnowledgebaseGrantModel.organization_id == organization_id,
                KnowledgebaseGrantModel.deleted.is_(False),
                KnowledgebaseModel.organization_id == organization_id,
                KnowledgebaseModel.deleted.is_(False),
            )
            .order_by(KnowledgebaseGrantModel.knowledgebase_id)
        )
        return list(result.scalars().all())

    # ---- internals ---------------------------------------------------

    async def _require_agent(self, agent_id: UUID, organization_id: UUID) -> None:
        result = await self.session.execute(
            select(AgentsModel.id).where(
                AgentsModel.id == agent_id,
                AgentsModel.organization_id == organization_id,
                AgentsModel.deleted.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise KnowledgebaseNotFound("Agent not found.")

    async def _require_scope_owner(
        self,
        scope: KnowledgeScope,
        scope_id: str,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> str:
        try:
            owner_id = UUID(scope_id)
        except ValueError:
            raise KnowledgebaseNotFound("Knowledgebase scope not found.") from None

        if scope is KnowledgeScope.ORGANIZATION:
            if str(owner_id) != str(organization_id):
                raise KnowledgebaseNotFound("Knowledgebase scope not found.")
        elif scope is KnowledgeScope.AGENT:
            await self._require_agent(owner_id, organization_id)
        elif scope is KnowledgeScope.CONVERSATION:
            query = select(ConversationsModel.id).where(
                ConversationsModel.id == owner_id,
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
            )
            if for_update:
                query = query.with_for_update()
            conversation_id = await self.session.scalar(
                query
            )
            if conversation_id is None:
                raise KnowledgebaseNotFound("Knowledgebase scope not found.")
        return str(owner_id)

    async def _find_grant(
        self,
        organization_id: UUID,
        agent_id: UUID,
        knowledgebase_id: UUID,
    ) -> KnowledgebaseGrantModel | None:
        result = await self.session.execute(
            select(KnowledgebaseGrantModel).where(
                KnowledgebaseGrantModel.agent_id == agent_id,
                KnowledgebaseGrantModel.knowledgebase_id == knowledgebase_id,
                KnowledgebaseGrantModel.organization_id == organization_id,
                KnowledgebaseGrantModel.deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()
