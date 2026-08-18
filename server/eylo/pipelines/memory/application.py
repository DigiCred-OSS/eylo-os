"""Three-level memory use cases composed with the configured adapter."""

from __future__ import annotations

import logging
from time import monotonic
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from eylo.common.contracts.memory import (
    Memory,
    MemoryActor,
    MemoryActorKind,
    MemoryError,
    MemoryInputMessage,
    MemoryLevel,
    MemoryMessageRole,
    MemoryOperation,
    MemoryOrigin,
    MemoryProvenance,
    MemoryRecall,
    MemoryScope,
    MemorySourceReference,
    require_memory_fact,
    require_memory_query,
)
from eylo.common.contracts.messages import MessageKind
from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.common.contracts.reranking import RankingMetadata, RankingState
from eylo.common.database import async_session_factory
from eylo.events.schema.py_events.memory import (
    MemoryFactAction,
    MemoryObservationOutcome,
    MemoryRecallObservedEvent,
)
from eylo.modules.memory.conflicts import MemoryConflictReader
from eylo.modules.memory.events import (
    emit_direct_memory_change,
    emit_direct_memory_changes,
    emit_memory_observation,
)
from eylo.modules.memory.scope import (
    authorized_scopes_from_context,
    scope_for_level,
)
from eylo.modules.memory.service import record_recalled_memories
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.memory.resolver import resolve_memory_adapter
from eylo.pipelines.reranking import RerankingRuntime, resolve_reranker
from eylo.pipelines.reranking.application import bounded_rerank

logger = logging.getLogger(__name__)

MAX_MEMORY_RERANK_CANDIDATES = 32


async def recall_context_memory(
    conversation_context,
    query: str,
    *,
    db=None,
    limit: int,
) -> MemoryRecall:
    started_at = monotonic()
    try:
        result = await _recall_context_memory(
            conversation_context,
            query,
            db=db,
            limit=limit,
        )
    except Exception as error:
        _publish_recall_observation(
            conversation_context=conversation_context,
            limit=limit,
            started_at=started_at,
            outcome=MemoryObservationOutcome.FAILED,
            ranking=RankingMetadata(
                state=RankingState.NOT_REQUESTED,
                comparable=False,
                candidate_count=0,
                returned_count=0,
            ),
            conflict_count=0,
            failure_code=_recall_failure_code(error),
        )
        raise

    _publish_recall_observation(
        conversation_context=conversation_context,
        limit=limit,
        started_at=started_at,
        outcome=(
            MemoryObservationOutcome.DEGRADED
            if result.ranking.state is RankingState.DEGRADED
            else MemoryObservationOutcome.SUCCEEDED
        ),
        ranking=result.ranking,
        conflict_count=len(result.conflicts),
        failure_code=None,
    )
    return result


async def _recall_context_memory(
    conversation_context,
    query: str,
    *,
    db=None,
    limit: int,
) -> MemoryRecall:
    """Recall one globally ranked union of authorized memory levels."""
    scopes = authorized_scopes_from_context(conversation_context)
    if not scopes:
        raise MemoryError("Memory context is unavailable.")
    conversation_id = _conversation_id(conversation_context)
    _agent_actor(conversation_context, conversation_id)
    normalized_query = require_memory_query(query)
    config_id, config_revision = memory_binding_from_context(conversation_context)
    adapter = await resolve_memory_adapter(
        scopes[0].organization_id,
        db,
        provider_config_id=config_id,
        provider_config_revision=config_revision,
    )
    reranking_binding = _reranking_binding_from_context(conversation_context)
    reranker, resolution_reason = await _resolve_requested_reranker(
        scopes[0].organization_id,
        reranking_binding,
        db=db,
    )
    candidate_limit, pre_degraded_reason = _candidate_limit(
        limit,
        reranker,
    )
    memories = await adapter.search(
        normalized_query,
        scopes=scopes,
        limit=candidate_limit,
    )
    if resolution_reason is not None:
        selected = memories[:limit]
        ranking = _unavailable_ranking(
            reranking_binding,
            reason=resolution_reason,
            candidate_count=len(memories),
            returned_count=len(selected),
        )
    else:
        outcome = await bounded_rerank(
            normalized_query,
            [memory.content for memory in memories],
            reranker,
            top_k=limit,
            pre_degraded_reason=pre_degraded_reason,
        )
        ranking = outcome.metadata
        selected = (
            memories[:limit]
            if outcome.selections is None
            else [memories[selection.index] for selection in outcome.selections]
        )
    try:
        async with async_session_factory() as conflict_session:
            conflicts = await MemoryConflictReader(conflict_session).for_recalled(
                organization_id=scopes[0].organization_id,
                scopes=tuple(scopes),
                memory_ids=[memory.id for memory in selected],
                limit=limit,
            )
    except MemoryError:
        raise
    except SQLAlchemyError as error:
        logger.warning("Memory conflict projection failed: %s", type(error).__name__)
        raise MemoryError(
            "Memory conflict evidence is unavailable.",
            retryable=True,
        ) from None
    try:
        async with async_session_factory() as recall_session:
            await record_recalled_memories(recall_session, selected)
            await recall_session.commit()
    except Exception as error:  # noqa: BLE001 - visibility cannot fail a reply
        logger.warning("Memory recall audit failed: %s", type(error).__name__)
    return MemoryRecall(memories=selected, conflicts=conflicts, ranking=ranking)


async def remember_context_fact(
    conversation_context,
    fact: str,
    *,
    level: MemoryLevel,
    db=None,
) -> list[MemoryOperation]:
    """Apply one deliberate fact to an exact context-derived level."""
    scope = scope_for_level(conversation_context, level)
    if scope is None:
        raise MemoryError("Memory context is unavailable.")
    normalized = require_memory_fact(fact)

    conversation_id = _conversation_id(conversation_context)
    source = _latest_user_source(conversation_context, conversation_id)
    actor = _agent_actor(conversation_context, conversation_id)
    config_id, config_revision = memory_binding_from_context(conversation_context)
    adapter = await resolve_memory_adapter(
        scope.organization_id,
        db,
        provider_config_id=config_id,
        provider_config_revision=config_revision,
    )
    operations = await adapter.add(
        [
            MemoryInputMessage(
                role=MemoryMessageRole.USER,
                content=normalized,
                sources=(source,),
            )
        ],
        scope=scope,
        source_conversation_id=conversation_id,
        origin=MemoryOrigin.AGENT_TOOL,
        actor=actor,
    )
    emit_direct_memory_changes(
        scope=scope,
        memory_provider_config_id=config_id,
        memory_provider_config_revision=config_revision,
        operations=operations,
    )
    return operations


async def refresh_context_fact(
    conversation_context,
    memory_id: UUID,
    fact: str,
    *,
    level: MemoryLevel,
    db=None,
) -> Memory:
    """Refresh one active fact inside its exact derived level."""
    normalized = require_memory_fact(fact)
    scope = _required_scope(conversation_context, level)
    provenance = _direct_agent_provenance(conversation_context)
    config_id, config_revision = memory_binding_from_context(conversation_context)
    adapter = await resolve_memory_adapter(
        scope.organization_id,
        db,
        provider_config_id=config_id,
        provider_config_revision=config_revision,
    )
    result = await adapter.update(
        memory_id,
        normalized,
        scope=scope,
        provenance=provenance,
    )
    if result.changed:
        emit_direct_memory_change(
            scope=scope,
            memory_provider_config_id=config_id,
            memory_provider_config_revision=config_revision,
            memory_id=result.memory.id,
            action=MemoryFactAction.UPDATED,
        )
    return result.memory


async def forget_context_fact(
    conversation_context,
    memory_id: UUID,
    *,
    level: MemoryLevel,
    db=None,
) -> bool:
    """Expire one active fact inside its exact derived level."""
    scope = _required_scope(conversation_context, level)
    provenance = _direct_agent_provenance(conversation_context)
    config_id, config_revision = memory_binding_from_context(conversation_context)
    adapter = await resolve_memory_adapter(
        scope.organization_id,
        db,
        provider_config_id=config_id,
        provider_config_revision=config_revision,
    )
    expired = await adapter.expire(
        memory_id,
        scope=scope,
        provenance=provenance,
    )
    if expired:
        emit_direct_memory_change(
            scope=scope,
            memory_provider_config_id=config_id,
            memory_provider_config_revision=config_revision,
            memory_id=memory_id,
            action=MemoryFactAction.EXPIRED,
        )
    return expired


def _recall_failure_code(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "memory_not_configured"
    if isinstance(error, MemoryError):
        return "memory_recall_failed"
    return "memory_recall_internal_failure"


def _publish_recall_observation(
    *,
    conversation_context,
    limit: int,
    started_at: float,
    outcome: MemoryObservationOutcome,
    ranking: RankingMetadata,
    conflict_count: int,
    failure_code: str | None,
) -> None:
    try:
        agent = conversation_context.primary_agent
        emit_memory_observation(
            MemoryRecallObservedEvent(
                organization_id=agent.organization_id,
                agent_id=agent.id,
                conversation_id=_conversation_id(conversation_context),
                outcome=outcome,
                requested_limit=limit,
                candidate_count=ranking.candidate_count,
                returned_count=ranking.returned_count,
                conflict_count=conflict_count,
                ranking_state=ranking.state,
                ranking_reason=ranking.reason,
                duration_ms=max(0, int((monotonic() - started_at) * 1000)),
                failure_code=failure_code,
            )
        )
    except Exception as error:  # noqa: BLE001 - observation cannot fail Memory
        logger.warning(
            "Memory recall observation unavailable error_type=%s",
            type(error).__name__,
        )


def memory_binding_from_context(conversation_context) -> tuple[UUID, int]:
    """Return the exact published agent binding used by this conversation turn."""
    agent = getattr(conversation_context, "primary_agent", None)
    config_id = getattr(agent, "memory_provider_config_id", None)
    revision = getattr(agent, "memory_provider_config_revision", None)
    if config_id is None or revision is None:
        raise NotConfiguredError(
            capability=Capability.MEMORY,
            missing=["published_agent_binding"],
            configure_via="/api/agents",
        )
    return UUID(str(config_id)), int(revision)


def _reranking_binding_from_context(
    conversation_context,
) -> tuple[UUID, int | None] | None:
    agent = getattr(conversation_context, "primary_agent", None)
    config_id = getattr(agent, "reranking_provider_config_id", None)
    if config_id is None:
        return None
    revision = getattr(agent, "reranking_provider_config_revision", None)
    try:
        normalized_revision = int(revision) if revision is not None else None
    except (TypeError, ValueError):
        normalized_revision = None
    if normalized_revision is not None and normalized_revision < 1:
        normalized_revision = None
    return UUID(str(config_id)), normalized_revision


async def _resolve_requested_reranker(
    organization_id: UUID,
    binding: tuple[UUID, int | None] | None,
    *,
    db,
) -> tuple[RerankingRuntime | None, str | None]:
    if binding is None:
        return None, None
    config_id, revision = binding
    if revision is None:
        return None, "configuration_unavailable"
    try:
        runtime = await resolve_reranker(
            organization_id,
            provider_config_id=config_id,
            provider_config_revision=revision,
            db=db,
        )
    except (NotConfiguredError, ProviderConfigError) as error:
        logger.warning(
            "Memory reranking unavailable config_id=%s revision=%s error_type=%s",
            config_id,
            revision,
            type(error).__name__,
        )
        return None, "configuration_unavailable"
    return runtime, None


def _candidate_limit(
    limit: int,
    reranker: RerankingRuntime | None,
) -> tuple[int, str | None]:
    if reranker is None:
        return limit, None
    budget = reranker.adapter.capabilities.max_documents
    if budget < limit:
        return limit, "candidate_budget_exceeded"
    overfetch = max(limit, min(MAX_MEMORY_RERANK_CANDIDATES, limit * 4))
    return min(overfetch, budget), None


def _unavailable_ranking(
    binding: tuple[UUID, int | None] | None,
    *,
    reason: str,
    candidate_count: int,
    returned_count: int,
) -> RankingMetadata:
    if binding is None:
        raise MemoryError("Memory reranking authority is unavailable.")
    config_id, revision = binding
    return RankingMetadata(
        state=RankingState.DEGRADED,
        comparable=False,
        reason=reason,
        provider=None,
        provider_config_id=config_id,
        provider_config_revision=revision,
        candidate_count=candidate_count,
        returned_count=returned_count,
    )


def _required_scope(
    conversation_context,
    level: MemoryLevel,
) -> MemoryScope:
    scope = scope_for_level(conversation_context, level)
    if scope is None:
        raise MemoryError("Memory context is unavailable.")
    return scope


def _conversation_id(conversation_context) -> UUID:
    conversation = getattr(conversation_context, "conversation", None)
    conversation_id = getattr(conversation, "id", None)
    if conversation_id is None:
        raise MemoryError("Memory source conversation is unavailable.")
    return UUID(str(conversation_id))


def _direct_agent_provenance(conversation_context) -> MemoryProvenance:
    conversation_id = _conversation_id(conversation_context)
    return MemoryProvenance(
        origin=MemoryOrigin.AGENT_TOOL,
        source_conversation_id=conversation_id,
        source_messages=(
            _latest_user_source(conversation_context, conversation_id),
        ),
        actor=_agent_actor(conversation_context, conversation_id),
        formation_job_id=None,
        extraction=None,
    )


def _latest_user_source(
    conversation_context,
    conversation_id: UUID,
) -> MemorySourceReference:
    participants = _participants_by_id(conversation_context, conversation_id)
    messages = sorted(
        getattr(conversation_context, "messages", None) or [],
        key=lambda message: (message.created_at, str(message.id)),
        reverse=True,
    )
    for message in messages:
        if message.kind != MessageKind.USER:
            continue
        participant = participants.get(message.sender_participant_id)
        if participant is None:
            raise MemoryError("Memory source participant is unavailable.")
        return _source_reference(message.id, participant)
    raise MemoryError("Memory source message is unavailable.")


def _agent_actor(conversation_context, conversation_id: UUID) -> MemoryActor:
    participant = conversation_context.get_primary_agent()
    agent = getattr(conversation_context, "primary_agent", None)
    if (
        participant is None
        or agent is None
        or participant.conversation_id != conversation_id
        or participant.agent_id != agent.id
        or participant.agent_revision is None
    ):
        raise MemoryError("Memory agent provenance is unavailable.")
    return MemoryActor(
        kind=MemoryActorKind.AGENT_PARTICIPANT,
        actor_id=participant.id,
        agent_id=participant.agent_id,
        agent_revision=participant.agent_revision,
    )


def _participants_by_id(
    conversation_context, conversation_id: UUID
) -> dict[UUID, object]:
    participants = getattr(conversation_context, "participants", None) or []
    return {
        participant.id: participant
        for participant in participants
        if participant.conversation_id == conversation_id
    }


def _source_reference(message_id: UUID, participant) -> MemorySourceReference:
    return MemorySourceReference(
        message_id=message_id,
        participant_id=participant.id,
        agent_id=participant.agent_id,
        agent_revision=participant.agent_revision,
    )


__all__ = [
    "forget_context_fact",
    "memory_binding_from_context",
    "recall_context_memory",
    "refresh_context_fact",
    "remember_context_fact",
]
