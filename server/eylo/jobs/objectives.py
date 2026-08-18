"""Outbox nudge and compute cleanup for objective-origin AgentRuns.

The periodic trigger executes no objective or model work here. PostgreSQL
AgentRun rows are the outbox; Absurd owns execution claim, retry, heartbeat and
wait.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from eylo.common.database import async_session_factory, start_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import AgentRunLifecycle, AgentRunOriginKind
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.sandbox.models import SandboxSessionModel
from eylo.pipelines.sandbox.sessions import reap_expired, reap_orphans

logger = logging.getLogger(__name__)
SPAWN_BATCH = 100


async def recover_unbound_objective_agent_runs() -> dict[str, int]:
    """Idempotently bind queued objective runs that missed direct spawn."""
    async with start_transaction(ro=True) as session:
        rows = (
            await session.execute(
                select(AgentRunModel.organization_id, AgentRunModel.id)
                .where(
                    AgentRunModel.origin_kind == AgentRunOriginKind.OBJECTIVE,
                    AgentRunModel.lifecycle == AgentRunLifecycle.QUEUED,
                    AgentRunModel.absurd_task_id.is_(None),
                    AgentRunModel.deleted.is_(False),
                )
                .order_by(AgentRunModel.created_at, AgentRunModel.id)
                .limit(SPAWN_BATCH)
            )
        ).all()

    spawned = failed = 0
    for organization_id, run_id in rows:
        try:
            await spawn_agent_run(
                organization_id=organization_id,
                run_id=run_id,
            )
            spawned += 1
        except Exception as error:  # noqa: BLE001 - later sweep retries the row
            failed += 1
            logger.warning(
                "Objective AgentRun=%s remains unbound error_type=%s",
                run_id,
                type(error).__name__,
            )
    return {"found": len(rows), "spawned": spawned, "failed": failed}


async def reap_sandbox_resources() -> dict[str, int]:
    """Destroy expired and orphaned compute without touching AgentRun state."""
    reaped = await reap_expired()
    async with async_session_factory() as db:
        organizations = (
            (await db.execute(select(SandboxSessionModel.organization_id).distinct()))
            .scalars()
            .all()
        )
    orphaned = 0
    for organization_id in organizations:
        result = await reap_orphans(organization_id)
        orphaned += result["orphans_destroyed"]
    return {**reaped, "orphans_destroyed": orphaned}


__all__ = [
    "reap_sandbox_resources",
    "recover_unbound_objective_agent_runs",
]
