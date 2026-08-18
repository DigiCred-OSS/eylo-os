"""Periodic convergence between Absurd task state and AgentRun product state."""

from __future__ import annotations

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.absurd import AgentRunAbsurdAdapter
from eylo.modules.agent_runs.domain import AgentRunLifecycle
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.agent_runs.service import (
    AgentRunConflict,
    AgentRunNotFound,
    accept_agent_run_cancellation,
)
from eylo.pipelines.conversation.run_failure import (
    fail_agent_run_and_converge_message,
)

_NONTERMINAL_LIFECYCLES = (
    AgentRunLifecycle.QUEUED,
    AgentRunLifecycle.RUNNING,
    AgentRunLifecycle.WAITING_FOR_INPUT,
    AgentRunLifecycle.WAITING_FOR_APPROVAL,
)
_FAILED_ENGINE_SUMMARY = "Durable execution exhausted its retry attempts."
_COMPLETED_ENGINE_SUMMARY = (
    "Durable execution completed without committing a product result."
)


async def reconcile_terminal_agent_runs(*, limit: int = 500) -> dict[str, int]:
    """Converge bound nonterminal runs after their engine task becomes terminal."""
    if isinstance(limit, bool) or not 1 <= limit <= 10_000:
        raise ValueError("AgentRun reconciliation limit must be between 1 and 10000.")

    async with start_transaction(ro=True) as session:
        rows = list(
            (
                await session.execute(
                    select(
                        AgentRunModel.id,
                        AgentRunModel.organization_id,
                        AgentRunModel.absurd_task_id,
                        AgentRunModel.cancellation_requested_at,
                    )
                    .where(
                        AgentRunModel.lifecycle.in_(_NONTERMINAL_LIFECYCLES),
                        AgentRunModel.absurd_task_id.is_not(None),
                        AgentRunModel.deleted.is_(False),
                    )
                    .order_by(AgentRunModel.created_at)
                    .limit(limit)
                )
            ).all()
        )

    counts = {"checked": 0, "failed": 0, "cancelled": 0, "raced": 0}
    adapter = AgentRunAbsurdAdapter()
    try:
        for row in rows:
            task_id = row.absurd_task_id
            if task_id is None:
                continue
            engine_state = await adapter.task_state(task_id=task_id)
            counts["checked"] += 1
            if engine_state not in {"cancelled", "completed", "failed"}:
                continue
            try:
                if engine_state == "cancelled" or row.cancellation_requested_at:
                    await accept_agent_run_cancellation(
                        organization_id=row.organization_id,
                        run_id=row.id,
                    )
                    counts["cancelled"] += 1
                    continue
                summary = (
                    _FAILED_ENGINE_SUMMARY
                    if engine_state == "failed"
                    else _COMPLETED_ENGINE_SUMMARY
                )
                await fail_agent_run_and_converge_message(
                    organization_id=row.organization_id,
                    run_id=row.id,
                    failure_summary=summary,
                )
                counts["failed"] += 1
            except (AgentRunConflict, AgentRunNotFound):
                # The product command won a race after this read. The next tick
                # sees its committed state; no engine claim is created here.
                counts["raced"] += 1
    finally:
        await adapter.close()
    return counts


__all__ = ["reconcile_terminal_agent_runs"]
