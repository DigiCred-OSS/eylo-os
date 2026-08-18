"""PostgreSQL recovery for message-linked conversation AgentRuns."""

from __future__ import annotations

import logging

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import AgentRunLifecycle, AgentRunOriginKind
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.schemas.messages import MessageKind

logger = logging.getLogger(__name__)

SPAWN_BATCH = 100


async def recover_unbound_conversation_agent_runs() -> dict[str, int]:
    """Bind queued user-message runs without inferring work from messages."""
    async with start_transaction(ro=True) as session:
        rows = tuple(
            (
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
                        MessagesModel.kind == MessageKind.USER,
                        MessagesModel.deleted.is_(False),
                    )
                    .order_by(AgentRunModel.created_at)
                    .limit(SPAWN_BATCH)
                )
            ).all()
        )

    spawned = 0
    failed = 0
    for organization_id, run_id in rows:
        try:
            await spawn_agent_run(
                organization_id=organization_id,
                run_id=run_id,
            )
            spawned += 1
        except Exception as error:  # noqa: BLE001 - next DB sweep retries the nudge
            failed += 1
            logger.warning(
                "Conversation AgentRun=%s remains unbound error_type=%s",
                run_id,
                type(error).__name__,
            )
    return {"found": len(rows), "spawned": spawned, "failed": failed}


__all__ = ["recover_unbound_conversation_agent_runs"]
