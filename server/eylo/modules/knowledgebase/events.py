"""Knowledgebase-owned publication helpers for local domain events."""

import logging
from collections.abc import Callable, Sequence
from uuid import UUID

from eylo.common.contracts.knowledgebase import KnowledgeAccess
from eylo.common.database import register_ephemeral_event_post_txn
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.knowledgebase import (
    KnowledgeCorpusImportLifecycleEvent,
    KnowledgeIngestionLifecycleEvent,
    KnowledgePostCommitEvent,
    KnowledgeQueryObservedEvent,
    KnowledgeReindexLifecycleEvent,
    KnowledgeReindexTransition,
    KnowledgeWorkTransition,
    KnowledgebaseAccessChangedEvent,
    KnowledgebaseAccessTransition,
    KnowledgebaseChangedField,
    KnowledgebaseLifecycleEvent,
    KnowledgebaseTransition,
)

logger = logging.getLogger(__name__)


def register_knowledgebase_lifecycle(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
    transition: KnowledgebaseTransition,
    changed_fields: Sequence[KnowledgebaseChangedField] = (),
    affected_ingestion_jobs: int = 0,
    affected_corpus_imports: int = 0,
    affected_reindex_jobs: int = 0,
    deleted_chunks: int = 0,
    revoked_grants: int = 0,
) -> bool:
    return _register_knowledge_event_post_commit(
        "KnowledgebaseLifecycleEvent",
        lambda: KnowledgebaseLifecycleEvent(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            transition=transition,
            changed_fields=tuple(changed_fields),
            affected_ingestion_jobs=affected_ingestion_jobs,
            affected_corpus_imports=affected_corpus_imports,
            affected_reindex_jobs=affected_reindex_jobs,
            deleted_chunks=deleted_chunks,
            revoked_grants=revoked_grants,
        ),
    )


def register_knowledgebase_access_changed(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
    agent_id: UUID,
    transition: KnowledgebaseAccessTransition,
    access: KnowledgeAccess | None,
) -> bool:
    return _register_knowledge_event_post_commit(
        "KnowledgebaseAccessChangedEvent",
        lambda: KnowledgebaseAccessChangedEvent(
            organization_id=organization_id,
            knowledgebase_id=knowledgebase_id,
            agent_id=agent_id,
            transition=transition,
            access=access,
        ),
    )


def emit_knowledge_observation(event: KnowledgeQueryObservedEvent) -> bool:
    """Publish one best-effort in-process Knowledgebase observation."""
    return emit_ephemeral(event)


def register_ingestion_lifecycle(
    job,
    transition: KnowledgeWorkTransition,
    *,
    failure_code: str | None = None,
) -> bool:
    """Project one committed ingestion-row transition into a local event."""
    return _register_knowledge_event_post_commit(
        "KnowledgeIngestionLifecycleEvent",
        lambda: KnowledgeIngestionLifecycleEvent(
            organization_id=job.organization_id,
            knowledgebase_id=job.knowledgebase_id,
            job_id=job.id,
            document_id=job.document_id,
            corpus_import_id=job.corpus_import_id,
            transition=transition,
            state=job.state.value,
            attempts=job.attempts,
            failure_code=failure_code,
        ),
    )


def register_corpus_lifecycle(
    record,
    transition: KnowledgeWorkTransition,
    *,
    failure_code: str | None = None,
) -> bool:
    """Project one committed corpus-row transition into a local event."""
    return _register_knowledge_event_post_commit(
        "KnowledgeCorpusImportLifecycleEvent",
        lambda: KnowledgeCorpusImportLifecycleEvent(
            organization_id=record.organization_id,
            knowledgebase_id=record.knowledgebase_id,
            import_id=record.id,
            transition=transition,
            state=record.state.value,
            attempts=record.attempts,
            discovered_count=record.discovered_count,
            queued_count=record.queued_count,
            skipped_count=int((record.skipped or {}).get("total", 0)),
            failure_code=failure_code,
        ),
    )


def register_reindex_lifecycle(
    job,
    transition: KnowledgeReindexTransition,
    *,
    index_state,
    failure_code: str | None = None,
) -> bool:
    """Project one committed reindex-row transition into a local event."""
    return _register_knowledge_event_post_commit(
        "KnowledgeReindexLifecycleEvent",
        lambda: KnowledgeReindexLifecycleEvent(
            organization_id=job.organization_id,
            knowledgebase_id=job.knowledgebase_id,
            job_id=job.id,
            transition=transition,
            state=job.state.value,
            index_state=index_state.value,
            source_embedding_space_id=job.source_embedding_space_id,
            target_embedding_space_id=job.target_embedding_space_id,
            processed_count=job.indexed_chunk_count,
            total_count=job.source_chunk_count,
            failure_code=failure_code,
        ),
    )


def _register_knowledge_event_post_commit(
    event_name: str,
    factory: Callable[[], KnowledgePostCommitEvent],
) -> bool:
    """Never let local observability become canonical transaction authority."""
    try:
        register_ephemeral_event_post_txn(factory())
    except Exception as error:  # noqa: BLE001 - product commit remains authority
        logger.warning(
            "Knowledgebase local event unavailable name=%s error_type=%s",
            event_name,
            type(error).__name__,
        )
        return False
    return True
