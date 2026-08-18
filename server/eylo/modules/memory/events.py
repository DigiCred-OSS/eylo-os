"""Memory-owned publication helpers for local domain events."""

import logging
from collections.abc import Callable, Iterable, Sequence
from uuid import UUID

from eylo.common.contracts.memory import (
    MemoryEvent,
    MemoryLevel,
    MemoryOperation,
    MemoryOrigin,
    MemoryScope,
)
from eylo.common.database import register_ephemeral_event_post_txn
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.memory import (
    MemoryFactAction,
    MemoryFactReference,
    MemoryFactsChangedEvent,
    MemoryFormationLifecycleEvent,
    MemoryOutcomeSummary,
    MemoryPostCommitEvent,
    MemoryRecallObservedEvent,
    MemoryReconciliationLifecycleEvent,
    MemoryReconciliationTransition,
    MemoryReindexLifecycleEvent,
    MemoryReindexTransition,
    MemoryWorkTransition,
)

logger = logging.getLogger(__name__)

_FACT_ACTIONS = {
    MemoryEvent.ADD: MemoryFactAction.ADDED,
    MemoryEvent.UPDATE: MemoryFactAction.UPDATED,
    MemoryEvent.EXPIRE: MemoryFactAction.EXPIRED,
    MemoryEvent.DELETE: MemoryFactAction.DELETED,
}


def emit_committed_memory_change(event: MemoryFactsChangedEvent) -> bool:
    """Publish a change after an adapter-owned transaction has returned."""
    return emit_ephemeral(event)


def emit_memory_observation(event: MemoryRecallObservedEvent) -> bool:
    """Publish one best-effort in-process Memory observation."""
    return emit_ephemeral(event)


def emit_direct_memory_changes(
    *,
    scope: MemoryScope,
    memory_provider_config_id: UUID,
    memory_provider_config_revision: int,
    operations: Sequence[MemoryOperation],
) -> bool:
    """Publish committed adapter outcomes without allowing event failure upstream."""
    try:
        changes = _operation_references(operations)
        if not changes:
            return False
        return emit_committed_memory_change(
            MemoryFactsChangedEvent(
                organization_id=scope.organization_id,
                memory_provider_config_id=memory_provider_config_id,
                memory_provider_config_revision=memory_provider_config_revision,
                level=scope.level,
                owner_id=scope.owner_id,
                source=MemoryOrigin.AGENT_TOOL,
                changes=changes,
            )
        )
    except Exception as error:  # noqa: BLE001 - adapter commit is already authority
        logger.warning(
            "Committed Memory change observation unavailable error_type=%s",
            type(error).__name__,
        )
        return False


def emit_direct_memory_change(
    *,
    scope: MemoryScope,
    memory_provider_config_id: UUID,
    memory_provider_config_revision: int,
    memory_id: UUID,
    action: MemoryFactAction,
) -> bool:
    """Publish one committed direct correction or expiry."""
    try:
        return emit_committed_memory_change(
            MemoryFactsChangedEvent(
                organization_id=scope.organization_id,
                memory_provider_config_id=memory_provider_config_id,
                memory_provider_config_revision=memory_provider_config_revision,
                level=scope.level,
                owner_id=scope.owner_id,
                source=MemoryOrigin.AGENT_TOOL,
                changes=(MemoryFactReference(memory_id=memory_id, action=action),),
            )
        )
    except Exception as error:  # noqa: BLE001 - adapter commit is already authority
        logger.warning(
            "Committed Memory change observation unavailable error_type=%s",
            type(error).__name__,
        )
        return False


def register_formation_lifecycle(
    job,
    transition: MemoryWorkTransition,
    *,
    outcomes=None,
    failure_code: str | None = None,
) -> bool:
    def build() -> MemoryFormationLifecycleEvent:
        outcome_summary = (
            MemoryOutcomeSummary(
                considered=outcomes.considered,
                added=outcomes.added,
                updated=outcomes.updated,
                deleted=outcomes.deleted,
                noop=outcomes.noop,
                failed=outcomes.failed,
            )
            if outcomes is not None
            else None
        )
        return MemoryFormationLifecycleEvent(
            organization_id=job.organization_id,
            job_id=job.id,
            conversation_id=job.conversation_id,
            memory_provider_config_id=job.memory_provider_config_id,
            memory_provider_config_revision=job.memory_provider_config_revision,
            transition=transition,
            state=job.state.value,
            attempts=job.attempts,
            outcomes=outcome_summary,
            failure_code=failure_code,
        )

    return _register_memory_event_post_commit(
        "MemoryFormationLifecycleEvent",
        build,
    )


def register_formation_fact_changes(
    job,
    operations: Sequence[MemoryOperation],
) -> bool:
    try:
        changes = _operation_references(operations)
    except Exception as error:  # noqa: BLE001 - product commit remains authority
        _log_registration_failure("MemoryFactsChangedEvent", error)
        return False
    if not changes:
        return False
    return _register_memory_event_post_commit(
        "MemoryFactsChangedEvent",
        lambda: MemoryFactsChangedEvent(
            organization_id=job.organization_id,
            memory_provider_config_id=job.memory_provider_config_id,
            memory_provider_config_revision=job.memory_provider_config_revision,
            level=MemoryLevel.CONVERSATION,
            owner_id=job.conversation_id,
            source=MemoryOrigin.AUTOMATIC_FORMATION,
            changes=changes,
            formation_job_id=job.id,
        ),
    )


def register_reconciliation_lifecycle(
    job,
    transition: MemoryReconciliationTransition,
    *,
    failure_code: str | None = None,
) -> bool:
    return _register_memory_event_post_commit(
        "MemoryReconciliationLifecycleEvent",
        lambda: MemoryReconciliationLifecycleEvent(
            organization_id=job.organization_id,
            job_id=job.id,
            memory_provider_config_id=job.memory_provider_config_id,
            memory_provider_config_revision=job.memory_provider_config_revision,
            level=job.scope_level,
            owner_id=job.owner_id,
            generation=job.generation,
            transition=transition,
            state=job.state.value,
            attempts=job.attempts,
            considered_count=job.considered_count,
            duplicate_count=job.duplicate_count,
            superseded_count=job.superseded_count,
            conflict_count=job.conflict_count,
            unrelated_count=job.unrelated_count,
            failed_count=job.failed_count,
            failure_code=failure_code,
        ),
    )


def register_reconciliation_expirations(
    job,
    memory_ids: Iterable[UUID],
) -> bool:
    try:
        changes = tuple(
            MemoryFactReference(memory_id=memory_id, action=MemoryFactAction.EXPIRED)
            for memory_id in memory_ids
        )
    except Exception as error:  # noqa: BLE001 - product commit remains authority
        _log_registration_failure("MemoryFactsChangedEvent", error)
        return False
    if not changes:
        return False
    return _register_memory_event_post_commit(
        "MemoryFactsChangedEvent",
        lambda: MemoryFactsChangedEvent(
            organization_id=job.organization_id,
            memory_provider_config_id=job.memory_provider_config_id,
            memory_provider_config_revision=job.memory_provider_config_revision,
            level=job.scope_level,
            owner_id=job.owner_id,
            source=MemoryOrigin.AUTOMATIC_RECONCILIATION,
            changes=changes,
            reconciliation_job_id=job.id,
        ),
    )


def register_reindex_lifecycle(
    index,
    transition: MemoryReindexTransition,
    *,
    job=None,
    source_embedding_space_id: str | None = None,
    target_embedding_space_id: str | None = None,
    failure_code: str | None = None,
) -> bool:
    def build() -> MemoryReindexLifecycleEvent:
        source_space_id = source_embedding_space_id or (
            job.source_embedding_space_id if job else index.embedding_space_id
        )
        target_space_id = target_embedding_space_id or (
            job.target_embedding_space_id if job else index.target_embedding_space_id
        )
        if source_space_id is None or target_space_id is None:
            raise ValueError("Memory reindex observation has no exact space fence.")
        return MemoryReindexLifecycleEvent(
            organization_id=index.organization_id,
            memory_provider_config_id=index.memory_provider_config_id,
            job_id=job.id if job else None,
            transition=transition,
            state=job.state.value if job else None,
            index_state=index.reindex_state.value,
            source_embedding_space_id=source_space_id,
            target_embedding_space_id=target_space_id,
            processed_count=job.indexed_fact_count if job else 0,
            total_count=job.source_fact_count if job else 0,
            failure_code=failure_code,
        )

    return _register_memory_event_post_commit(
        "MemoryReindexLifecycleEvent",
        build,
    )


def _register_memory_event_post_commit(
    event_name: str,
    factory: Callable[[], MemoryPostCommitEvent],
) -> bool:
    """Never let local observability become canonical transaction authority."""
    try:
        register_ephemeral_event_post_txn(factory())
    except Exception as error:  # noqa: BLE001 - product commit remains authority
        _log_registration_failure(event_name, error)
        return False
    return True


def _log_registration_failure(event_name: str, error: Exception) -> None:
    logger.warning(
        "Memory local event unavailable name=%s error_type=%s",
        event_name,
        type(error).__name__,
    )


def _operation_references(
    operations: Sequence[MemoryOperation],
) -> tuple[MemoryFactReference, ...]:
    references: list[MemoryFactReference] = []
    for operation in operations:
        action = _FACT_ACTIONS.get(operation.event)
        if action is None:
            continue
        if operation.target_id is None:
            raise ValueError("Committed Memory operation omitted its fact ID.")
        references.append(
            MemoryFactReference(memory_id=operation.target_id, action=action)
        )
    return tuple(references)
