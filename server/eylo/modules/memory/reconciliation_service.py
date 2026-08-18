"""Durable Memory reconciliation filing and atomic relationship outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import AbsurdBoundWorkService, DurableState
from eylo.common.contracts.embedding import embedding_space_from_record
from eylo.common.contracts.memory import (
    MemoryError,
    MemoryEvent,
    MemoryExtractionAuthority,
    MemoryLevel,
    MemoryOrigin,
    MemoryProvenance,
)
from eylo.common.contracts.memory_reconciliation import (
    MEMORY_RECONCILIATION_MAX_CHANGES,
    MemoryReconciliationBatch,
    MemoryReconciliationDecision,
    MemoryReconciliationInput,
    MemoryReconciliationOutcome,
    MemoryReconciliationProposal,
    MemoryReconciliationSettlement,
    MemoryReconciliationSettlementReason,
    MemoryRelationshipKind,
)
from eylo.durable_runtime import DURABLE_MAX_ATTEMPTS
from eylo.events.schema.py_events.memory import MemoryReconciliationTransition
from eylo.modules.memory.events import (
    register_reconciliation_expirations,
    register_reconciliation_lifecycle,
)
from eylo.modules.memory.models import (
    MemoryChangeModel,
    MemoryModel,
    MemoryReconciliationCursorModel,
    MemoryReconciliationEffectModel,
    MemoryReconciliationJobModel,
    MemoryRelationshipModel,
)
from eylo.modules.memory.reindex_service import MemoryReindexService


@dataclass(frozen=True, order=True, slots=True)
class ReconciliationPosition:
    created_at: datetime
    change_id: UUID


@dataclass(frozen=True, slots=True)
class ReconciliationCounts:
    considered: int
    duplicate: int
    superseded: int
    conflict: int
    unrelated: int
    failed: int = 0

    @classmethod
    def from_proposal(
        cls,
        proposal: MemoryReconciliationProposal,
    ) -> "ReconciliationCounts":
        decisions = proposal.decisions
        return cls(
            considered=len(decisions),
            duplicate=sum(
                decision.outcome is MemoryReconciliationOutcome.DUPLICATE
                for decision in decisions
            ),
            superseded=sum(
                decision.outcome is MemoryReconciliationOutcome.SUPERSEDES
                for decision in decisions
            ),
            conflict=sum(
                decision.outcome is MemoryReconciliationOutcome.CONFLICTS
                for decision in decisions
            ),
            unrelated=sum(
                decision.outcome is MemoryReconciliationOutcome.UNRELATED
                for decision in decisions
            ),
        )

    def job_values(self) -> dict[str, int]:
        return {
            "considered_count": self.considered,
            "duplicate_count": self.duplicate,
            "superseded_count": self.superseded,
            "conflict_count": self.conflict,
            "unrelated_count": self.unrelated,
            "failed_count": self.failed,
        }


class MemoryReconciliationStale(MemoryError):
    """An immutable proposal lost a fact revision and must be re-filed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class MemoryReconciliationService:
    """Own cursor ranges, immutable evidence, and revision-fenced effects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def backlog_cursor_ids(self, *, limit: int = 100) -> list[UUID]:
        rows = await self.session.scalars(
            select(MemoryReconciliationCursorModel.id)
            .where(
                MemoryReconciliationCursorModel.active_job_id.is_(None),
                MemoryReconciliationCursorModel.deleted.is_(False),
                or_(
                    MemoryReconciliationCursorModel.processed_through_created_at.is_(
                        None
                    ),
                    tuple_(
                        MemoryReconciliationCursorModel.requested_through_created_at,
                        MemoryReconciliationCursorModel.requested_through_change_id,
                    )
                    > tuple_(
                        MemoryReconciliationCursorModel.processed_through_created_at,
                        MemoryReconciliationCursorModel.processed_through_change_id,
                    ),
                ),
            )
            .order_by(MemoryReconciliationCursorModel.updated_at.asc())
            .limit(limit)
        )
        return list(rows.all())

    async def file_next(self, cursor_id: UUID) -> MemoryReconciliationJobModel | None:
        cursor = await self.session.scalar(
            select(MemoryReconciliationCursorModel)
            .where(
                MemoryReconciliationCursorModel.id == cursor_id,
                MemoryReconciliationCursorModel.active_job_id.is_(None),
                MemoryReconciliationCursorModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if cursor is None or not _cursor_has_backlog(cursor):
            return None

        changes = await self._next_changes(cursor)
        if not changes:
            raise MemoryError("Memory reconciliation cursor has no durable changes.")
        through = _change_position(changes[-1])
        processed = _cursor_position(cursor, requested=False)
        recorded_space = embedding_space_from_record(cursor)
        active_space = await MemoryReindexService(self.session).lock_active_space(
            organization_id=cursor.organization_id,
            memory_provider_config_id=cursor.memory_provider_config_id,
        )
        if recorded_space is None or not recorded_space.is_compatible_with(active_space):
            raise MemoryError("Memory reconciliation filing crossed an index cutover.")

        job = MemoryReconciliationJobModel(
            organization_id=cursor.organization_id,
            scope_level=cursor.scope_level,
            owner_id=cursor.owner_id,
            **_owner_fields(cursor.scope_level, cursor.owner_id),
            generation=cursor.next_generation,
            range_start_created_at=(
                None if processed is None else processed.created_at
            ),
            range_start_change_id=None if processed is None else processed.change_id,
            range_through_created_at=through.created_at,
            range_through_change_id=through.change_id,
            change_count=len(changes),
            memory_provider_config_id=cursor.memory_provider_config_id,
            memory_provider_config_revision=cursor.memory_provider_config_revision,
            embedding_provider_config_id=cursor.embedding_provider_config_id,
            embedding_provider_config_revision=(
                cursor.embedding_provider_config_revision
            ),
            embedding_provider=cursor.embedding_provider,
            embedding_endpoint=cursor.embedding_endpoint,
            embedding_model=cursor.embedding_model,
            embedding_dimensions=cursor.embedding_dimensions,
            embedding_semantic_options=dict(cursor.embedding_semantic_options),
            embedding_space_id=cursor.embedding_space_id,
            reconciliation_llm_provider_config_id=(
                cursor.reconciliation_llm_provider_config_id
            ),
            reconciliation_llm_provider_config_revision=(
                cursor.reconciliation_llm_provider_config_revision
            ),
            reconciliation_llm_provider=cursor.reconciliation_llm_provider,
            reconciliation_llm_model=cursor.reconciliation_llm_model,
            reconciliation_prompt_revision=cursor.reconciliation_prompt_revision,
            max_attempts=DURABLE_MAX_ATTEMPTS,
        )
        self.session.add(job)
        await self.session.flush()
        cursor.active_job_id = job.id
        cursor.next_generation += 1
        await self.session.flush()
        register_reconciliation_lifecycle(
            job,
            MemoryReconciliationTransition.QUEUED,
        )
        return job

    async def begin_attempt(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReconciliationJobModel:
        job = await AbsurdBoundWorkService(
            MemoryReconciliationJobModel,
            self.session,
        ).begin_attempt(work_id=job_id, organization_id=organization_id)
        if job.state not in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            register_reconciliation_lifecycle(
                job,
                MemoryReconciliationTransition.ATTEMPT_STARTED,
            )
        return job

    async def running_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReconciliationJobModel:
        job = await AbsurdBoundWorkService(
            MemoryReconciliationJobModel,
            self.session,
        ).get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        if job.state not in {
            DurableState.RUNNING,
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            raise MemoryError("Memory reconciliation attempt is not running.")
        return job

    async def changes_for_job(
        self,
        job: MemoryReconciliationJobModel,
    ) -> list[MemoryChangeModel]:
        query = self._partition_changes(job).where(
            tuple_(MemoryChangeModel.created_at, MemoryChangeModel.id)
            <= tuple_(job.range_through_created_at, job.range_through_change_id)
        )
        if job.range_start_created_at is not None:
            query = query.where(
                tuple_(MemoryChangeModel.created_at, MemoryChangeModel.id)
                > tuple_(job.range_start_created_at, job.range_start_change_id)
            )
        changes = list(
            (
                await self.session.scalars(
                    query.order_by(
                        MemoryChangeModel.created_at.asc(),
                        MemoryChangeModel.id.asc(),
                    ).limit(MEMORY_RECONCILIATION_MAX_CHANGES + 1)
                )
            ).all()
        )
        if len(changes) != job.change_count:
            raise MemoryError("Memory reconciliation change range is inconsistent.")
        if not changes or _change_position(changes[-1]) != _job_through(job):
            raise MemoryError("Memory reconciliation watermark is inconsistent.")
        return changes

    async def build_batch_skeleton(
        self,
        job: MemoryReconciliationJobModel,
        changes: list[MemoryChangeModel],
    ) -> MemoryReconciliationBatch:
        evidence: dict[UUID, list[UUID]] = defaultdict(list)
        latest: dict[UUID, MemoryChangeModel] = {}
        order: list[UUID] = []
        for change in changes:
            if change.memory_id not in latest:
                order.append(change.memory_id)
            evidence[change.memory_id].append(change.id)
            latest[change.memory_id] = change

        facts = list(
            (
                await self.session.scalars(
                    select(MemoryModel).where(
                        MemoryModel.organization_id == job.organization_id,
                        MemoryModel.memory_provider_config_id
                        == job.memory_provider_config_id,
                        MemoryModel.id.in_(order),
                    )
                )
            ).all()
        )
        by_id = {fact.id: fact for fact in facts}
        inputs: list[MemoryReconciliationInput] = []
        settlements: list[MemoryReconciliationSettlement] = []
        now = datetime.now(timezone.utc)
        for memory_id in order:
            fact = by_id.get(memory_id)
            change = latest[memory_id]
            if (
                fact is None
                or not _matches_partition(fact, job)
                or fact.state_revision != change.memory_state_revision
                or fact.reconciled_state_revision >= fact.state_revision
            ):
                continue
            change_ids = tuple(evidence[memory_id])
            if fact.deleted:
                settlements.append(
                    MemoryReconciliationSettlement(
                        memory_id=fact.id,
                        state_revision=fact.state_revision,
                        evidence_change_ids=change_ids,
                        reason=MemoryReconciliationSettlementReason.DELETED,
                    )
                )
            elif fact.expires_at is not None and fact.expires_at <= now:
                settlements.append(
                    MemoryReconciliationSettlement(
                        memory_id=fact.id,
                        state_revision=fact.state_revision,
                        evidence_change_ids=change_ids,
                        reason=MemoryReconciliationSettlementReason.EXPIRED,
                    )
                )
            else:
                inputs.append(
                    MemoryReconciliationInput(
                        memory_id=fact.id,
                        state_revision=fact.state_revision,
                        content=fact.content,
                        evidence_change_ids=change_ids,
                        candidates=(),
                    )
                )
        return MemoryReconciliationBatch(
            inputs=tuple(inputs),
            settlements=tuple(settlements),
        )

    async def store_batch(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        batch: MemoryReconciliationBatch,
    ) -> MemoryReconciliationEffectModel:
        effect = await self.session.scalar(
            select(MemoryReconciliationEffectModel)
            .where(
                MemoryReconciliationEffectModel.organization_id == organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id == job_id,
                MemoryReconciliationEffectModel.deleted.is_(False),
            )
            .with_for_update()
        )
        payload = batch.model_dump(mode="json")
        if effect is None:
            effect = MemoryReconciliationEffectModel(
                organization_id=organization_id,
                reconciliation_job_id=job_id,
                inputs=payload,
            )
            self.session.add(effect)
            await self.session.flush()
        elif effect.inputs != payload:
            raise MemoryError("Memory reconciliation immutable inputs changed.")
        return effect

    async def load_batch(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReconciliationBatch | None:
        payload = await self.session.scalar(
            select(MemoryReconciliationEffectModel.inputs).where(
                MemoryReconciliationEffectModel.organization_id == organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id == job_id,
                MemoryReconciliationEffectModel.deleted.is_(False),
            )
        )
        if payload is None:
            return None
        try:
            return MemoryReconciliationBatch.model_validate(payload)
        except ValidationError:
            raise MemoryError("Memory reconciliation stored inputs are invalid.") from None

    async def store_proposal(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        proposal: MemoryReconciliationProposal,
    ) -> None:
        effect = await self._locked_effect(organization_id, job_id)
        payload = proposal.model_dump(mode="json")
        if effect.proposal is None:
            effect.proposal = payload
            await self.session.flush()
        elif effect.proposal != payload:
            raise MemoryError("Memory reconciliation immutable proposal changed.")

    async def load_proposal(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReconciliationProposal | None:
        payload = await self.session.scalar(
            select(MemoryReconciliationEffectModel.proposal).where(
                MemoryReconciliationEffectModel.organization_id == organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id == job_id,
                MemoryReconciliationEffectModel.deleted.is_(False),
            )
        )
        if payload is None:
            return None
        try:
            return MemoryReconciliationProposal.model_validate(payload)
        except ValidationError:
            raise MemoryError("Memory reconciliation stored proposal is invalid.") from None

    async def apply(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        batch: MemoryReconciliationBatch,
        proposal: MemoryReconciliationProposal,
    ) -> MemoryReconciliationJobModel:
        work = AbsurdBoundWorkService(MemoryReconciliationJobModel, self.session)
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        if job.state is DurableState.SUCCEEDED:
            return job
        if job.state is not DurableState.RUNNING:
            raise MemoryError("Memory reconciliation apply is not running.")
        cursor = await self._locked_cursor(job)
        effect = await self._locked_effect(organization_id, job_id)
        if effect.finished_at is not None:
            raise MemoryError("Memory reconciliation effect finished before its job.")
        if effect.inputs != batch.model_dump(mode="json"):
            raise MemoryError("Memory reconciliation apply inputs changed.")
        if effect.proposal != proposal.model_dump(mode="json"):
            raise MemoryError("Memory reconciliation apply proposal changed.")

        decisions = _validate_complete_proposal(batch, proposal)
        expire_ids, retained_ids = _effect_sets(decisions)
        if expire_ids & retained_ids:
            raise MemoryError("Memory reconciliation proposal has conflicting effects.")

        expected = _expected_fact_revisions(batch, decisions)
        facts = list(
            (
                await self.session.scalars(
                    select(MemoryModel)
                    .where(
                        MemoryModel.organization_id == organization_id,
                        MemoryModel.id.in_(sorted(expected, key=str)),
                    )
                    .order_by(MemoryModel.id.asc())
                    .with_for_update()
                )
            ).all()
        )
        by_id = {fact.id: fact for fact in facts}
        if set(by_id) != set(expected):
            raise MemoryReconciliationStale(
                "Memory reconciliation fact set changed."
            )
        _validate_locked_facts(job, batch, expected, by_id)

        provenance = _reconciliation_provenance(job)
        changes: list[MemoryChangeModel] = []
        relationships: list[MemoryRelationshipModel] = []
        decision_inputs = {item.memory_id: item for item in batch.inputs}
        now = datetime.now(timezone.utc)
        for operation_index, decision in enumerate(decisions):
            source = by_id[decision.memory_id]
            related = (
                None
                if decision.related_memory_id is None
                else by_id[decision.related_memory_id]
            )
            if decision.outcome is MemoryReconciliationOutcome.DUPLICATE:
                _expire_fact(source, provenance, now)
                changes.append(
                    _expiry_change(job, source, provenance, operation_index)
                )
                relationships.append(
                    _relationship(
                        job,
                        kind=MemoryRelationshipKind.DUPLICATE_OF,
                        source=source,
                        target=related,
                        evidence=decision_inputs[source.id].evidence_change_ids,
                    )
                )
            elif decision.outcome is MemoryReconciliationOutcome.SUPERSEDES:
                _expire_fact(related, provenance, now)
                changes.append(
                    _expiry_change(job, related, provenance, operation_index)
                )
                source.reconciled_state_revision = source.state_revision
                relationships.append(
                    _relationship(
                        job,
                        kind=MemoryRelationshipKind.SUPERSEDED_BY,
                        source=related,
                        target=source,
                        evidence=decision_inputs[source.id].evidence_change_ids,
                    )
                )
            elif decision.outcome is MemoryReconciliationOutcome.CONFLICTS:
                source.reconciled_state_revision = source.state_revision
                relationships.append(
                    _relationship(
                        job,
                        kind=MemoryRelationshipKind.CONFLICTS_WITH,
                        source=source,
                        target=related,
                        evidence=decision_inputs[source.id].evidence_change_ids,
                    )
                )
            else:
                source.reconciled_state_revision = source.state_revision

        for settlement in batch.settlements:
            by_id[settlement.memory_id].reconciled_state_revision = (
                settlement.state_revision
            )

        self.session.add_all([*changes, *relationships])
        await self.session.flush()
        for change in changes:
            _advance_requested_cursor(cursor, _change_position(change))
        _advance_processed_cursor(cursor, job)
        cursor.active_job_id = None

        counts = ReconciliationCounts.from_proposal(proposal)
        effect.outcomes = {
            "counts": counts.job_values(),
            "settled_count": len(batch.settlements),
            "change_ids": [str(change.id) for change in changes],
            "relationship_ids": [str(row.id) for row in relationships],
        }
        effect.finished_at = now
        row = await work.succeed(
            work_id=job_id,
            organization_id=organization_id,
            values=counts.job_values(),
        )
        await self.session.flush()
        register_reconciliation_lifecycle(
            row,
            MemoryReconciliationTransition.SUCCEEDED,
        )
        register_reconciliation_expirations(
            row,
            (change.memory_id for change in changes),
        )
        return row

    async def fail(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        error: str,
        permanent: bool,
    ) -> MemoryReconciliationJobModel:
        work = AbsurdBoundWorkService(MemoryReconciliationJobModel, self.session)
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = job.state is DurableState.RUNNING
        state = await work.fail(
            work_id=job_id,
            organization_id=organization_id,
            error=error,
            permanent=permanent,
        )
        if state is DurableState.FAILED:
            job.considered_count = 1
            job.failed_count = 1
            if was_running:
                cursor = await self._locked_cursor(job)
                requested = _cursor_position(cursor, requested=True)
                if requested is not None and requested > _job_through(job):
                    cursor.active_job_id = None
        await self.session.flush()
        if was_running:
            register_reconciliation_lifecycle(
                job,
                (
                    MemoryReconciliationTransition.RETRY_SCHEDULED
                    if state is DurableState.PENDING
                    else MemoryReconciliationTransition.FAILED
                ),
                failure_code=error,
            )
        return job

    async def abandon_stale(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        error: str,
    ) -> tuple[MemoryReconciliationJobModel, UUID]:
        """Fail one stale snapshot and reopen its unchanged cursor range."""
        work = AbsurdBoundWorkService(MemoryReconciliationJobModel, self.session)
        current = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        was_running = current.state is DurableState.RUNNING
        await work.fail(
            work_id=job_id,
            organization_id=organization_id,
            error=error,
            permanent=True,
        )
        job = await work.get(
            work_id=job_id,
            organization_id=organization_id,
            for_update=True,
        )
        cursor = await self._locked_cursor(job)
        job.considered_count = 1
        job.failed_count = 1
        cursor.active_job_id = None
        await self.session.flush()
        if was_running:
            register_reconciliation_lifecycle(
                job,
                MemoryReconciliationTransition.STALE_ABANDONED,
                failure_code=error,
            )
        return job, cursor.id

    async def _next_changes(
        self,
        cursor: MemoryReconciliationCursorModel,
    ) -> list[MemoryChangeModel]:
        requested = _cursor_position(cursor, requested=True)
        if requested is None:
            return []
        query = self._partition_changes(cursor).where(
            tuple_(MemoryChangeModel.created_at, MemoryChangeModel.id)
            <= tuple_(requested.created_at, requested.change_id)
        )
        processed = _cursor_position(cursor, requested=False)
        if processed is not None:
            query = query.where(
                tuple_(MemoryChangeModel.created_at, MemoryChangeModel.id)
                > tuple_(processed.created_at, processed.change_id)
            )
        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        MemoryChangeModel.created_at.asc(),
                        MemoryChangeModel.id.asc(),
                    ).limit(MEMORY_RECONCILIATION_MAX_CHANGES)
                )
            ).all()
        )

    def _partition_changes(self, owner):
        level = MemoryLevel(owner.scope_level)
        owner_column = getattr(MemoryChangeModel, _owner_column(level))
        return select(MemoryChangeModel).where(
            MemoryChangeModel.organization_id == owner.organization_id,
            MemoryChangeModel.memory_provider_config_id
            == owner.memory_provider_config_id,
            MemoryChangeModel.scope_level == level,
            owner_column == owner.owner_id,
            MemoryChangeModel.deleted.is_(False),
        )

    async def _locked_effect(
        self,
        organization_id: UUID,
        job_id: UUID,
    ) -> MemoryReconciliationEffectModel:
        effect = await self.session.scalar(
            select(MemoryReconciliationEffectModel)
            .where(
                MemoryReconciliationEffectModel.organization_id == organization_id,
                MemoryReconciliationEffectModel.reconciliation_job_id == job_id,
                MemoryReconciliationEffectModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if effect is None:
            raise MemoryError("Memory reconciliation effect is unavailable.")
        return effect

    async def _locked_cursor(
        self,
        job: MemoryReconciliationJobModel,
    ) -> MemoryReconciliationCursorModel:
        cursor = await self.session.scalar(
            select(MemoryReconciliationCursorModel)
            .where(
                MemoryReconciliationCursorModel.organization_id
                == job.organization_id,
                MemoryReconciliationCursorModel.active_job_id == job.id,
                MemoryReconciliationCursorModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if cursor is None:
            raise MemoryError("Memory reconciliation job lost its cursor fence.")
        return cursor


def _owner_column(level: MemoryLevel) -> str:
    return {
        MemoryLevel.AGENT: "agent_id",
        MemoryLevel.USER: "contact_id",
        MemoryLevel.CONVERSATION: "conversation_id",
    }[level]


def _owner_fields(level: MemoryLevel, owner_id: UUID) -> dict[str, UUID | None]:
    values: dict[str, UUID | None] = {
        "agent_id": None,
        "contact_id": None,
        "conversation_id": None,
    }
    values[_owner_column(MemoryLevel(level))] = owner_id
    return values


def _cursor_position(
    cursor: MemoryReconciliationCursorModel,
    *,
    requested: bool,
) -> ReconciliationPosition | None:
    created_at = (
        cursor.requested_through_created_at
        if requested
        else cursor.processed_through_created_at
    )
    change_id = (
        cursor.requested_through_change_id
        if requested
        else cursor.processed_through_change_id
    )
    if created_at is None and change_id is None:
        return None
    if created_at is None or change_id is None:
        raise MemoryError("Memory reconciliation cursor watermark is incomplete.")
    return ReconciliationPosition(created_at=created_at, change_id=change_id)


def _cursor_has_backlog(cursor: MemoryReconciliationCursorModel) -> bool:
    requested = _cursor_position(cursor, requested=True)
    processed = _cursor_position(cursor, requested=False)
    return requested is not None and (processed is None or requested > processed)


def _change_position(change: MemoryChangeModel) -> ReconciliationPosition:
    return ReconciliationPosition(created_at=change.created_at, change_id=change.id)


def _job_through(job: MemoryReconciliationJobModel) -> ReconciliationPosition:
    return ReconciliationPosition(
        created_at=job.range_through_created_at,
        change_id=job.range_through_change_id,
    )


def _matches_partition(fact: MemoryModel, owner) -> bool:
    level = MemoryLevel(owner.scope_level)
    return (
        fact.organization_id == owner.organization_id
        and fact.memory_provider_config_id == owner.memory_provider_config_id
        and MemoryLevel(fact.scope_level) is level
        and getattr(fact, _owner_column(level)) == owner.owner_id
        and fact.embedding_space_id == owner.embedding_space_id
    )


def _validate_complete_proposal(
    batch: MemoryReconciliationBatch,
    proposal: MemoryReconciliationProposal,
) -> tuple[MemoryReconciliationDecision, ...]:
    inputs = {item.memory_id: item for item in batch.inputs}
    decisions = proposal.decisions
    if len(decisions) != len(inputs) or {row.memory_id for row in decisions} != set(
        inputs
    ):
        raise MemoryError("Memory reconciliation proposal is incomplete.")
    for decision in decisions:
        source = inputs[decision.memory_id]
        if decision.observed_state_revision != source.state_revision:
            raise MemoryError("Memory reconciliation source revision changed.")
        candidates = {item.memory_id: item for item in source.candidates}
        if decision.outcome is MemoryReconciliationOutcome.UNRELATED:
            continue
        candidate = candidates.get(decision.related_memory_id)
        if (
            candidate is None
            or decision.related_state_revision != candidate.state_revision
        ):
            raise MemoryError("Memory reconciliation candidate revision changed.")
    return decisions


def _effect_sets(
    decisions: tuple[MemoryReconciliationDecision, ...],
) -> tuple[set[UUID], set[UUID]]:
    expire_ids: list[UUID] = []
    retained: set[UUID] = set()
    for decision in decisions:
        if decision.outcome is MemoryReconciliationOutcome.DUPLICATE:
            expire_ids.append(decision.memory_id)
            retained.add(decision.related_memory_id)
        elif decision.outcome is MemoryReconciliationOutcome.SUPERSEDES:
            expire_ids.append(decision.related_memory_id)
            retained.add(decision.memory_id)
        elif decision.outcome is MemoryReconciliationOutcome.CONFLICTS:
            retained.update((decision.memory_id, decision.related_memory_id))
        else:
            retained.add(decision.memory_id)
    if len(expire_ids) != len(set(expire_ids)):
        raise MemoryError("Memory reconciliation expires one fact more than once.")
    return set(expire_ids), retained


def _expected_fact_revisions(
    batch: MemoryReconciliationBatch,
    decisions: tuple[MemoryReconciliationDecision, ...],
) -> dict[UUID, int]:
    expected = {
        item.memory_id: item.state_revision
        for item in (*batch.inputs, *batch.settlements)
    }
    for decision in decisions:
        if decision.related_memory_id is None:
            continue
        prior = expected.setdefault(
            decision.related_memory_id,
            decision.related_state_revision,
        )
        if prior != decision.related_state_revision:
            raise MemoryError("Memory reconciliation repeats a conflicting revision.")
    return expected


def _validate_locked_facts(
    job: MemoryReconciliationJobModel,
    batch: MemoryReconciliationBatch,
    expected: dict[UUID, int],
    facts: dict[UUID, MemoryModel],
) -> None:
    now = datetime.now(timezone.utc)
    active_snapshots = {
        item.memory_id: item for item in batch.inputs
    } | {
        candidate.memory_id: candidate
        for item in batch.inputs
        for candidate in item.candidates
    }
    settlements = {item.memory_id: item for item in batch.settlements}
    for memory_id, revision in expected.items():
        fact = facts[memory_id]
        if not _matches_partition(fact, job) or fact.state_revision != revision:
            raise MemoryReconciliationStale(
                "Memory reconciliation lost a fact revision."
            )
        snapshot = active_snapshots.get(memory_id)
        if snapshot is not None:
            if (
                fact.deleted
                or (fact.expires_at is not None and fact.expires_at <= now)
                or fact.content != snapshot.content
            ):
                raise MemoryReconciliationStale(
                    "Memory reconciliation active fact changed."
                )
            continue
        settlement = settlements[memory_id]
        if settlement.reason is MemoryReconciliationSettlementReason.DELETED:
            valid = fact.deleted
        else:
            valid = fact.expires_at is not None and fact.expires_at <= now
        if not valid:
            raise MemoryReconciliationStale(
                "Memory reconciliation lifecycle settlement changed."
            )


def _reconciliation_provenance(
    job: MemoryReconciliationJobModel,
) -> MemoryProvenance:
    return MemoryProvenance(
        origin=MemoryOrigin.AUTOMATIC_RECONCILIATION,
        source_conversation_id=None,
        source_messages=(),
        actor=None,
        formation_job_id=None,
        reconciliation_job_id=job.id,
        extraction=MemoryExtractionAuthority(
            provider_config_id=job.reconciliation_llm_provider_config_id,
            provider_config_revision=(
                job.reconciliation_llm_provider_config_revision
            ),
            provider=job.reconciliation_llm_provider,
            model=job.reconciliation_llm_model,
            prompt_revision=job.reconciliation_prompt_revision,
        ),
    )


def _expire_fact(
    fact: MemoryModel | None,
    provenance: MemoryProvenance,
    now: datetime,
) -> None:
    if fact is None:
        raise MemoryError("Memory reconciliation related fact is unavailable.")
    fact.expires_at = now
    fact.provenance = provenance.model_dump(mode="json")
    fact.state_revision += 1
    fact.reconciled_state_revision = fact.state_revision
    fact.updated_at = now


def _expiry_change(
    job: MemoryReconciliationJobModel,
    fact: MemoryModel | None,
    provenance: MemoryProvenance,
    operation_index: int,
) -> MemoryChangeModel:
    if fact is None:
        raise MemoryError("Memory reconciliation expiry fact is unavailable.")
    return MemoryChangeModel(
        memory_id=fact.id,
        organization_id=job.organization_id,
        scope_level=job.scope_level,
        **_owner_fields(job.scope_level, job.owner_id),
        source_conversation_id=None,
        event=MemoryEvent.EXPIRE,
        before=fact.content,
        after=None,
        provenance=provenance.model_dump(mode="json"),
        memory_state_revision=fact.state_revision,
        memory_provider_config_id=job.memory_provider_config_id,
        memory_provider_config_revision=job.memory_provider_config_revision,
        embedding_provider_config_id=job.embedding_provider_config_id,
        embedding_provider_config_revision=job.embedding_provider_config_revision,
        embedding_provider=job.embedding_provider,
        embedding_endpoint=job.embedding_endpoint,
        embedding_model=job.embedding_model,
        embedding_dimensions=job.embedding_dimensions,
        embedding_semantic_options=dict(job.embedding_semantic_options),
        embedding_space_id=job.embedding_space_id,
        reconciliation_llm_provider_config_id=(
            job.reconciliation_llm_provider_config_id
        ),
        reconciliation_llm_provider_config_revision=(
            job.reconciliation_llm_provider_config_revision
        ),
        reconciliation_llm_provider=job.reconciliation_llm_provider,
        reconciliation_llm_model=job.reconciliation_llm_model,
        reconciliation_prompt_revision=job.reconciliation_prompt_revision,
        formation_job_id=None,
        formation_operation_index=None,
        reconciliation_job_id=job.id,
        reconciliation_operation_index=operation_index,
    )


def _relationship(
    job: MemoryReconciliationJobModel,
    *,
    kind: MemoryRelationshipKind,
    source: MemoryModel | None,
    target: MemoryModel | None,
    evidence: tuple[UUID, ...],
) -> MemoryRelationshipModel:
    if source is None or target is None:
        raise MemoryError("Memory reconciliation relationship is incomplete.")
    return MemoryRelationshipModel(
        organization_id=job.organization_id,
        memory_provider_config_id=job.memory_provider_config_id,
        scope_level=job.scope_level,
        owner_id=job.owner_id,
        **_owner_fields(job.scope_level, job.owner_id),
        kind=kind,
        source_memory_id=source.id,
        source_state_revision=source.state_revision,
        target_memory_id=target.id,
        target_state_revision=target.state_revision,
        reconciliation_job_id=job.id,
        evidence_change_ids=[str(change_id) for change_id in evidence],
    )


def _advance_requested_cursor(
    cursor: MemoryReconciliationCursorModel,
    position: ReconciliationPosition,
) -> None:
    current = _cursor_position(cursor, requested=True)
    if current is None or position > current:
        cursor.requested_through_created_at = position.created_at
        cursor.requested_through_change_id = position.change_id


def _advance_processed_cursor(
    cursor: MemoryReconciliationCursorModel,
    job: MemoryReconciliationJobModel,
) -> None:
    current = _cursor_position(cursor, requested=False)
    expected = (
        None
        if job.range_start_created_at is None
        else ReconciliationPosition(
            created_at=job.range_start_created_at,
            change_id=job.range_start_change_id,
        )
    )
    if current != expected:
        raise MemoryError("Memory reconciliation processed watermark changed.")
    through = _job_through(job)
    requested = _cursor_position(cursor, requested=True)
    if requested is None or through > requested:
        raise MemoryError("Memory reconciliation processed beyond its request.")
    cursor.processed_through_created_at = through.created_at
    cursor.processed_through_change_id = through.change_id


__all__ = [
    "MemoryReconciliationStale",
    "MemoryReconciliationService",
    "ReconciliationCounts",
    "ReconciliationPosition",
]
