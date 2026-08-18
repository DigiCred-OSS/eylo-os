"""Search granted knowledgebases with honest optional reranking."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any

from eylo.common.contracts.knowledgebase import (
    MAX_KNOWLEDGE_QUERY_CHARS,
    MAX_KNOWLEDGE_RESULTS,
    MAX_KNOWLEDGE_SCOPE_FILTERS,
    KnowledgeScope,
)
from eylo.common.contracts.knowledgebase import KnowledgebaseError as VendorError
from eylo.common.contracts.provider_config import Capability
from eylo.common.contracts.reranking import (
    RankingMetadata,
    RankingState,
)
from eylo.common.database import get_transaction, start_transaction
from eylo.events.schema.py_events.knowledgebase import (
    KnowledgeObservationOutcome,
    KnowledgeQueryObservedEvent,
)
from eylo.modules.knowledgebase.access import readable_scopes
from eylo.modules.knowledgebase.events import emit_knowledge_observation
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.knowledgebase.resolver import resolve_adapter
from eylo.pipelines.reranking import RerankingRuntime, resolve_reranker
from eylo.pipelines.reranking.application import bounded_rerank

logger = logging.getLogger(__name__)

MAX_RERANK_CANDIDATES_PER_KNOWLEDGEBASE = 32


@dataclass(frozen=True)
class _Search:
    knowledgebase: Any
    adapter: Any
    scopes: Any
    limit: int


@dataclass(frozen=True, slots=True)
class _QueryObservation:
    outcome: KnowledgeObservationOutcome
    requested_count: int
    available_count: int
    failed_count: int
    candidate_count: int
    returned_count: int
    ranking_state: RankingState
    ranking_reason: str | None
    failure_code: str | None = None


def _knowledgebase_unavailable_reason(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "not configured"
    if isinstance(error, KnowledgebaseError):
        return "configuration unavailable"
    return "provider unavailable"


async def query_agent_knowledge(
    *,
    query: str,
    scopes: list[str] | None,
    agent,
    conversation_id=None,
    top_k: int = MAX_KNOWLEDGE_RESULTS,
) -> dict[str, Any]:
    started_at = monotonic()
    valid_request = _valid_query_request(query, scopes, top_k)
    try:
        result = await _query_agent_knowledge(
            query=query,
            scopes=scopes,
            agent=agent,
            conversation_id=conversation_id,
            top_k=top_k,
        )
    except Exception as error:
        if valid_request:
            _publish_query_observation(
                agent=agent,
                conversation_id=conversation_id,
                started_at=started_at,
                observation=_QueryObservation(
                    outcome=KnowledgeObservationOutcome.FAILED,
                    requested_count=0,
                    available_count=0,
                    failed_count=0,
                    candidate_count=0,
                    returned_count=0,
                    ranking_state=RankingState.NOT_REQUESTED,
                    ranking_reason=None,
                    failure_code=_query_failure_code(error),
                ),
            )
        raise

    observation = result.pop("_local_observation", None)
    if isinstance(observation, _QueryObservation):
        _publish_query_observation(
            agent=agent,
            conversation_id=conversation_id,
            started_at=started_at,
            observation=observation,
        )
    return result


async def _query_agent_knowledge(
    *,
    query: str,
    scopes: list[str] | None,
    agent,
    conversation_id=None,
    top_k: int = MAX_KNOWLEDGE_RESULTS,
) -> dict[str, Any]:
    if not query.strip() or len(query) > MAX_KNOWLEDGE_QUERY_CHARS:
        return {
            "success": False,
            "results": [],
            "message": (
                "Query must be non-empty and no longer than "
                f"{MAX_KNOWLEDGE_QUERY_CHARS} characters."
            ),
        }
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_KNOWLEDGE_RESULTS:
        return {
            "success": False,
            "results": [],
            "message": f"top_k must be between 1 and {MAX_KNOWLEDGE_RESULTS}.",
        }
    requested_scopes = _parse_scopes(scopes)
    if requested_scopes is False:
        return {
            "success": False,
            "results": [],
            "message": "Scopes must be any of: organization, agent, conversation.",
        }

    async with start_transaction(ro=True):
        session = get_transaction()
        grants = await KnowledgebaseService(session).grants_for_agent(
            agent.id,
            agent.organization_id,
        )
        reranker = await _resolve_requested_reranker(agent, session)
        if not grants:
            ranking = _empty_ranking(reranker)
            return {
                "success": True,
                "results": [],
                "message": "No knowledgebase is available to this agent.",
                "ranking": ranking.model_dump(mode="json"),
                "_local_observation": _QueryObservation(
                    outcome=KnowledgeObservationOutcome.SUCCEEDED,
                    requested_count=0,
                    available_count=0,
                    failed_count=0,
                    candidate_count=0,
                    returned_count=0,
                    ranking_state=ranking.state,
                    ranking_reason=ranking.reason,
                ),
            }

        base_limit, pre_degraded_reason = _candidate_limit(
            len(grants),
            reranker,
            top_k=top_k,
        )
        searches: list[_Search] = []
        unavailable: list[tuple[str, str]] = []
        for grant in grants:
            knowledgebase = grant.knowledgebase
            scope_map = readable_scopes(
                grant,
                requested=requested_scopes,
                conversation_id=conversation_id,
            )
            if not scope_map:
                continue
            try:
                adapter = await resolve_adapter(
                    knowledgebase,
                    organization_id=agent.organization_id,
                    session=session,
                )
            except (NotConfiguredError, KnowledgebaseError, VendorError) as error:
                unavailable.append(
                    (knowledgebase.name, _knowledgebase_unavailable_reason(error))
                )
                logger.warning(
                    "Knowledgebase unavailable id=%s error_type=%s",
                    knowledgebase.id,
                    type(error).__name__,
                )
                continue
            searches.append(
                _Search(
                    knowledgebase=knowledgebase,
                    adapter=adapter,
                    scopes=scope_map,
                    limit=base_limit,
                )
            )

    outcomes = await asyncio.gather(
        *(
            search.adapter.query(
                query,
                scopes=search.scopes,
                limit=search.limit,
            )
            for search in searches
        ),
        return_exceptions=True,
    )

    groups: list[list[dict[str, Any]]] = []
    for search, outcome in zip(searches, outcomes):
        if isinstance(outcome, Exception):
            unavailable.append((search.knowledgebase.name, "query failed"))
            logger.warning(
                "Knowledgebase query failed id=%s error_type=%s",
                search.knowledgebase.id,
                type(outcome).__name__,
            )
            continue
        groups.append(
            [
                {
                    "document_id": result.document_id,
                    "content": result.content,
                    "title": result.title,
                    "source_uri": result.source_uri,
                    "scope": result.scope.value,
                    "scope_id": result.scope_id,
                    "score": result.score,
                    "knowledgebase_id": str(search.knowledgebase.id),
                    "knowledgebase": search.knowledgebase.name,
                }
                for result in outcome
            ]
        )

    results, ranking = await _rank(
        query,
        groups,
        reranker,
        top_k=top_k,
        pre_degraded_reason=pre_degraded_reason,
    )
    if unavailable and not results:
        return {
            "success": False,
            "results": [],
            "message": (
                "No knowledgebase could be searched. "
                + "; ".join(f"{name}: {reason}" for name, reason in unavailable)
            ),
            "ranking": ranking.model_dump(mode="json"),
            "_local_observation": _QueryObservation(
                outcome=KnowledgeObservationOutcome.FAILED,
                requested_count=len(grants),
                available_count=len(groups),
                failed_count=len(unavailable),
                candidate_count=ranking.candidate_count,
                returned_count=0,
                ranking_state=ranking.state,
                ranking_reason=ranking.reason,
                failure_code="knowledge_query_unavailable",
            ),
        }

    message = "" if results else "Nothing matched that query."
    if unavailable:
        message = (
            f"{message} Some knowledgebases could not be searched: "
            f"{', '.join(name for name, _ in unavailable)}."
        ).strip()
    return {
        "success": True,
        "results": results,
        "message": message,
        "ranking": ranking.model_dump(mode="json"),
        "_local_observation": _QueryObservation(
            outcome=(
                KnowledgeObservationOutcome.DEGRADED
                if unavailable or ranking.state is RankingState.DEGRADED
                else KnowledgeObservationOutcome.SUCCEEDED
            ),
            requested_count=len(grants),
            available_count=len(groups),
            failed_count=len(unavailable),
            candidate_count=ranking.candidate_count,
            returned_count=len(results),
            ranking_state=ranking.state,
            ranking_reason=ranking.reason,
        ),
    }


def _valid_query_request(
    query: str,
    scopes: list[str] | None,
    top_k: int,
) -> bool:
    return (
        bool(query.strip())
        and len(query) <= MAX_KNOWLEDGE_QUERY_CHARS
        and isinstance(top_k, int)
        and not isinstance(top_k, bool)
        and 1 <= top_k <= MAX_KNOWLEDGE_RESULTS
        and _parse_scopes(scopes) is not False
    )


def _query_failure_code(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "knowledge_reranking_not_configured"
    if isinstance(error, (KnowledgebaseError, VendorError)):
        return "knowledge_query_invalid"
    return "knowledge_query_failed"


def _publish_query_observation(
    *,
    agent,
    conversation_id,
    started_at: float,
    observation: _QueryObservation,
) -> None:
    try:
        emit_knowledge_observation(
            KnowledgeQueryObservedEvent(
                organization_id=agent.organization_id,
                agent_id=agent.id,
                conversation_id=conversation_id,
                outcome=observation.outcome,
                requested_knowledgebase_count=observation.requested_count,
                available_knowledgebase_count=observation.available_count,
                failed_knowledgebase_count=observation.failed_count,
                candidate_count=observation.candidate_count,
                returned_count=observation.returned_count,
                ranking_state=observation.ranking_state,
                ranking_reason=observation.ranking_reason,
                duration_ms=max(0, int((monotonic() - started_at) * 1000)),
                failure_code=observation.failure_code,
            )
        )
    except Exception as error:  # noqa: BLE001 - observation cannot fail the query
        logger.warning(
            "Knowledge query observation unavailable error_type=%s",
            type(error).__name__,
        )


async def _resolve_requested_reranker(agent, session) -> RerankingRuntime | None:
    config_id = agent.reranking_provider_config_id
    if config_id is None:
        return None
    revision = agent.reranking_provider_config_revision
    if revision is None:
        raise NotConfiguredError(
            capability=Capability.RERANKING,
            missing=["published_config_revision"],
            configure_via=f"/api/{agent.organization_id}/agents/{agent.id}",
        )
    return await resolve_reranker(
        agent.organization_id,
        provider_config_id=config_id,
        provider_config_revision=revision,
        db=session,
    )


def _candidate_limit(
    knowledgebase_count: int,
    reranker: RerankingRuntime | None,
    *,
    top_k: int,
) -> tuple[int, str | None]:
    if reranker is None:
        return top_k, None
    budget = reranker.adapter.capabilities.max_documents
    if knowledgebase_count > budget:
        return top_k, "candidate_budget_exceeded"
    fair_share = max(1, budget // knowledgebase_count)
    return min(MAX_RERANK_CANDIDATES_PER_KNOWLEDGEBASE, fair_share), None


async def _rank(
    query: str,
    groups: list[list[dict[str, Any]]],
    reranker: RerankingRuntime | None,
    *,
    top_k: int,
    pre_degraded_reason: str | None,
) -> tuple[list[dict[str, Any]], RankingMetadata]:
    candidates = [result for group in groups for result in group]
    outcome = await bounded_rerank(
        query,
        [item["content"] for item in candidates],
        reranker,
        top_k=top_k,
        pre_degraded_reason=pre_degraded_reason,
    )
    if outcome.selections is None:
        results = _interleave(groups, top_k)
    else:
        results = []
        for selection in outcome.selections:
            item = dict(candidates[selection.index])
            item["retrieval_score"] = item["score"]
            item["score"] = selection.score
            results.append(item)
    return _annotate(results, outcome.metadata), outcome.metadata


def _interleave(
    groups: list[list[dict[str, Any]]],
    limit: int,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    position = 0
    while len(ordered) < limit:
        added = False
        for group in groups:
            if position < len(group):
                ordered.append(dict(group[position]))
                added = True
                if len(ordered) == limit:
                    break
        if not added:
            break
        position += 1
    return ordered


def _annotate(
    results: list[dict[str, Any]],
    ranking: RankingMetadata,
) -> list[dict[str, Any]]:
    annotated = []
    for position, result in enumerate(results, start=1):
        label = f"K{position}"
        annotated.append(
            {
                **result,
                "citation": {
                    "label": label,
                    "knowledgebase_id": result["knowledgebase_id"],
                    "document_id": result["document_id"],
                    "title": result["title"],
                    "source_uri": result["source_uri"],
                },
                "ranking_state": ranking.state.value,
                "score_comparable": ranking.comparable,
            }
        )
    return annotated


def _empty_ranking(reranker: RerankingRuntime | None) -> RankingMetadata:
    return RankingMetadata(
        state=(RankingState.APPLIED if reranker else RankingState.NOT_REQUESTED),
        comparable=reranker is not None,
        reason="no_candidates" if reranker else None,
        provider=reranker.provider if reranker else None,
        provider_config_id=reranker.provider_config_id if reranker else None,
        provider_config_revision=(
            reranker.provider_config_revision if reranker else None
        ),
        candidate_count=0,
        returned_count=0,
    )


def _parse_scopes(scopes: list[str] | None) -> list[KnowledgeScope] | None | bool:
    if scopes is None:
        return None
    if len(scopes) > MAX_KNOWLEDGE_SCOPE_FILTERS:
        return False
    try:
        return [KnowledgeScope(name.strip().lower()) for name in scopes]
    except (AttributeError, ValueError):
        return False
