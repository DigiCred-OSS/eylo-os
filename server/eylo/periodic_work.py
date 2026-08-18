"""Durable PostgreSQL-backed trigger for periodic platform work."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext

from eylo.durable_runtime import PlatformDurableRuntime
from eylo.events.durable.binding import spawn_unbound_event_deliveries
from eylo.jobs.agent_runs import reconcile_terminal_agent_runs
from eylo.jobs.campaign_executor import process_campaign_calls
from eylo.jobs.deletion import nudge_unbound_deletions
from eylo.jobs.knowledge_ingestion import nudge_unbound_knowledge_work
from eylo.jobs.memory_formation import (
    nudge_unbound_memory_formations,
    nudge_unbound_memory_reconciliations,
    nudge_unbound_memory_reindexes,
)
from eylo.jobs.objectives import (
    reap_sandbox_resources,
    recover_unbound_objective_agent_runs,
)
from eylo.jobs.recording_upload import nudge_unbound_recording_uploads
from eylo.jobs.scheduler import dispatch_due_schedules, recover_stranded_schedules
from eylo.modules.connections.tasks import (
    cleanup_expired_oauth_states,
    cleanup_invalidated_connections,
)
from eylo.modules.conversations.tasks.agent_runs import (
    recover_unbound_conversation_agent_runs,
)
from eylo.modules.conversations.tasks.conversations import expire_old_conversations
from eylo.modules.parallel_agents.tasks import recover_unbound_parallel_agent_runs
from eylo.pipelines.integrations_v2.tasks import refresh_expiring_curated_tokens

logger = logging.getLogger(__name__)

PERIODIC_WORKFLOW = "eylo.periodic.tick.v1"
PERIODIC_IDEMPOTENCY_PREFIX = "eylo-periodic-tick:v1"
_MINUTE_SECONDS = 60

PeriodicCallable = Callable[[], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class PeriodicAction:
    name: str
    every_minutes: int
    run: PeriodicCallable


_ACTIONS = (
    PeriodicAction("dispatch-due-schedules", 1, dispatch_due_schedules),
    PeriodicAction("recover-stranded-schedules", 1, recover_stranded_schedules),
    PeriodicAction("reconcile-terminal-agent-runs", 1, reconcile_terminal_agent_runs),
    PeriodicAction(
        "recover-conversation-runs",
        1,
        recover_unbound_conversation_agent_runs,
    ),
    PeriodicAction("recover-parallel-runs", 1, recover_unbound_parallel_agent_runs),
    PeriodicAction("recover-objective-runs", 1, recover_unbound_objective_agent_runs),
    PeriodicAction("nudge-event-deliveries", 1, spawn_unbound_event_deliveries),
    PeriodicAction("nudge-knowledge-work", 1, nudge_unbound_knowledge_work),
    PeriodicAction("nudge-recording-uploads", 1, nudge_unbound_recording_uploads),
    PeriodicAction("process-campaign-calls", 1, process_campaign_calls),
    PeriodicAction("nudge-memory-reindexes", 1, nudge_unbound_memory_reindexes),
    PeriodicAction(
        "nudge-memory-reconciliations",
        1,
        nudge_unbound_memory_reconciliations,
    ),
    PeriodicAction("nudge-memory-formations", 5, nudge_unbound_memory_formations),
    PeriodicAction("nudge-deletions", 1, nudge_unbound_deletions),
    PeriodicAction("reap-sandbox-resources", 5, reap_sandbox_resources),
    PeriodicAction(
        "refresh-expiring-curated-tokens", 5, refresh_expiring_curated_tokens
    ),
    PeriodicAction("expire-old-conversations", 5, expire_old_conversations),
    PeriodicAction("cleanup-oauth-states", 60, cleanup_expired_oauth_states),
    PeriodicAction(
        "cleanup-invalidated-connections", 24 * 60, cleanup_invalidated_connections
    ),
)


def register_periodic_workflow(runtime: PlatformDurableRuntime) -> None:
    """Register the one durable cron-replacement workflow."""
    runtime.register_task(name=PERIODIC_WORKFLOW, handler=_run_periodic_tick)


async def seed_periodic_work(
    runtime: PlatformDurableRuntime,
    *,
    now: datetime | None = None,
) -> UUID:
    """Idempotently ensure the next UTC minute has one periodic trigger."""
    scheduled_for = _next_minute(now or datetime.now(timezone.utc))
    return await _spawn_tick(runtime, scheduled_for)


async def _run_periodic_tick(
    params: dict[str, Any],
    context: AsyncTaskContext,
) -> dict[str, Any]:
    scheduled_for = _scheduled_for(params)
    await context.sleep_until("scheduled", scheduled_for)

    next_scheduled = max(
        scheduled_for + timedelta(minutes=1),
        _next_minute(datetime.now(timezone.utc)),
    )
    await context.step(
        "spawn-next",
        lambda: _spawn_next_tick(next_scheduled),
    )

    minute_index = int(scheduled_for.timestamp() // _MINUTE_SECONDS)
    due = [action for action in _ACTIONS if minute_index % action.every_minutes == 0]
    completed: list[str] = []
    failed: list[str] = []
    for action in due:
        outcome = await context.step(
            f"action:{action.name}",
            lambda action=action: _run_action(action),
        )
        target = completed if outcome == "ok" else failed
        target.append(action.name)

    return {
        "scheduled_for": scheduled_for.isoformat(),
        "completed": completed,
        "failed": failed,
    }


async def _run_action(action: PeriodicAction) -> str:
    try:
        await action.run()
    except Exception as error:  # noqa: BLE001 - later ticks retry DB-backed work
        logger.error(
            "Periodic action failed action=%s error_type=%s; later ticks remain independent",
            action.name,
            type(error).__name__,
        )
        return "failed"
    return "ok"


async def _spawn_next_tick(scheduled_for: datetime) -> str:
    runtime = PlatformDurableRuntime()
    try:
        return str(await _spawn_tick(runtime, scheduled_for))
    finally:
        await runtime.close()


async def _spawn_tick(
    runtime: PlatformDurableRuntime,
    scheduled_for: datetime,
) -> UUID:
    timestamp = scheduled_for.isoformat()
    return await runtime.spawn_task(
        name=PERIODIC_WORKFLOW,
        params={"scheduled_for": timestamp},
        idempotency_key=f"{PERIODIC_IDEMPOTENCY_PREFIX}:{timestamp}",
    )


def _scheduled_for(params: dict[str, Any]) -> datetime:
    raw = params.get("scheduled_for")
    if not isinstance(raw, str):
        raise ValueError("Periodic task requires scheduled_for.")
    try:
        scheduled_for = datetime.fromisoformat(raw)
    except ValueError as error:
        raise ValueError("Periodic task scheduled_for must be ISO-8601.") from error
    if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
        raise ValueError("Periodic task scheduled_for must include a timezone.")
    return scheduled_for.astimezone(timezone.utc)


def _next_minute(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(
        minutes=1
    )


__all__ = [
    "PERIODIC_WORKFLOW",
    "register_periodic_workflow",
    "seed_periodic_work",
]
