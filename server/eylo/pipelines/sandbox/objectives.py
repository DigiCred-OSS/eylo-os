"""File direct objectives as canonical AgentRuns, then nudge Absurd."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import (
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
)
from eylo.modules.agent_runs.schemas import AgentRunRead
from eylo.modules.agent_runs.service import (
    file_objective_agent_run_in_transaction,
    get_agent_run,
)
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agents import build_executable_agent_resolver


async def create_objective_for_agent(
    *,
    organization_id: UUID,
    member_id: UUID,
    agent_id: UUID,
    goal: str,
    max_steps: int,
    deadline: datetime,
    idempotency_token: str,
) -> AgentRunRead:
    """Pin one published agent revision and atomically file its objective run."""
    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ValueError("Objective deadline must include a timezone.")

    async with start_transaction() as session:
        executable = await build_executable_agent_resolver(session).resolve_for_new_work(
            organization_id=organization_id,
            agent_id=agent_id,
            consumer_kind=TemplateConsumerKind.SANDBOX_AGENT,
        )
        filing = await file_objective_agent_run_in_transaction(
            session,
            organization_id=organization_id,
            principal=InitiatingPrincipalRef(
                organization_id=organization_id,
                kind=InitiatingPrincipalKind.MEMBER,
                principal_id=member_id,
            ),
            agent_id=executable.ref.definition_id,
            agent_revision=executable.ref.revision,
            goal=goal,
            context_manifest={
                "kind": "objective",
                "max_steps": max_steps,
                "deadline": deadline.isoformat(),
            },
            idempotency_token=idempotency_token,
        )

    await spawn_agent_run(
        organization_id=organization_id,
        run_id=filing.run_id,
    )
    return await get_agent_run(
        organization_id=organization_id,
        run_id=filing.run_id,
    )


__all__ = ["create_objective_for_agent"]
