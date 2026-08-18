"""Periodic nudge for queued parallel AgentRuns that missed direct spawn.

This function executes no agent work. PostgreSQL `AgentRun` rows are the outbox;
Absurd owns the only claim, retry, heartbeat and cancellation protocol.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import AgentRunLifecycle, AgentRunOriginKind
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.schemas.messages import MessageContentKind, MessageKind

logger = logging.getLogger(__name__)

SPAWN_BATCH = 100


async def recover_unbound_parallel_agent_runs() -> dict[str, int]:
    """Idempotently bind queued task-message runs to the Absurd workflow."""
    async with start_transaction(ro=True) as session:
        rows = (
            await session.execute(
                select(AgentRunModel.organization_id, AgentRunModel.id)
                .join(
                    MessagesModel,
                    MessagesModel.id == AgentRunModel.origin_message_id,
                )
                .where(
                    AgentRunModel.origin_kind == AgentRunOriginKind.MESSAGE,
                    AgentRunModel.lifecycle == AgentRunLifecycle.QUEUED,
                    AgentRunModel.absurd_task_id.is_(None),
                    AgentRunModel.deleted.is_(False),
                    MessagesModel.kind == MessageKind.SYSTEM,
                    MessagesModel.content_kind == MessageContentKind.TASK,
                    MessagesModel.deleted.is_(False),
                )
                .order_by(AgentRunModel.created_at)
                .limit(SPAWN_BATCH)
            )
        ).all()

    spawned = 0
    failed = 0
    for organization_id, run_id in rows:
        try:
            await spawn_agent_run(
                organization_id=organization_id,
                run_id=run_id,
            )
            spawned += 1
        except Exception as error:  # noqa: BLE001 - later sweep retries the outbox
            failed += 1
            logger.warning(
                "Parallel AgentRun=%s remains unbound error_type=%s",
                run_id,
                type(error).__name__,
            )
    return {"found": len(rows), "spawned": spawned, "failed": failed}


__all__ = ["recover_unbound_parallel_agent_runs"]
