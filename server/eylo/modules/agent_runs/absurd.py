"""Explicit Absurd 0.4.0 adapter for durable AgentRun execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext

from eylo.common.database import start_transaction
from eylo.durable_runtime import (
    DURABLE_CANCELLATION_POLICY,
    DURABLE_MAX_ATTEMPTS,
    DURABLE_QUEUE,
    DURABLE_RETRY_STRATEGY,
    AbsurdRuntimeConfig,
    DurableRuntimeConfigurationError,
    PlatformDurableRuntime,
)
from eylo.modules.agent_runs.domain import AgentRunLifecycle
from eylo.modules.agent_runs.repositories import AgentRunRepository
from eylo.modules.agent_runs.workflow import (
    AgentRunComputeCleanup,
    AgentRunExecutor,
    AgentRunFailureHandler,
    AgentRunWorkflow,
    UnwiredAgentRunExecutor,
)

AGENT_RUN_QUEUE = DURABLE_QUEUE
AGENT_RUN_WORKFLOW = "eylo.agent-runs.execute.v1"
AGENT_RUN_MAX_ATTEMPTS = DURABLE_MAX_ATTEMPTS
AGENT_RUN_RETRY_STRATEGY = DURABLE_RETRY_STRATEGY
AGENT_RUN_CANCELLATION_POLICY = DURABLE_CANCELLATION_POLICY
AgentRunRuntimeConfigurationError = DurableRuntimeConfigurationError


class AgentRunSpawnConflict(Exception):
    """A product run cannot be bound to the requested engine task."""


@dataclass(frozen=True, slots=True)
class AgentRunRegistrationHealth:
    """Public registration manifest without inspecting SDK private state."""

    registered: bool
    workflow_name: str
    queue_name: str
    max_attempts: int
    has_automatic_timeout: bool


@dataclass(frozen=True, slots=True)
class AgentRunTaskBinding:
    """Stable product-to-engine binding returned by idempotent spawn."""

    organization_id: UUID
    run_id: UUID
    task_id: UUID
    created: bool


class AgentRunAbsurdAdapter:
    """Own spawn/cancel/registration; Absurd alone owns claims and retries."""

    def __init__(
        self,
        config: AbsurdRuntimeConfig | None = None,
        *,
        runtime: PlatformDurableRuntime | None = None,
    ) -> None:
        if config is not None and runtime is not None:
            raise AgentRunRuntimeConfigurationError(
                "Pass an AgentRun runtime or config, not both."
            )
        self._runtime = runtime or PlatformDurableRuntime(config)
        self._owns_runtime = runtime is None
        self._config = self._runtime.config
        self._registration: AgentRunRegistrationHealth | None = None

    @property
    def runtime(self) -> PlatformDurableRuntime:
        """Expose the shared runtime to the process-level workflow registrar."""
        return self._runtime

    def register_workflow(
        self,
        executor: AgentRunExecutor | None = None,
        *,
        compute_cleanup: AgentRunComputeCleanup | None = None,
        failure_handler: AgentRunFailureHandler | None = None,
    ) -> AgentRunRegistrationHealth:
        if self._registration is not None:
            raise AgentRunRuntimeConfigurationError(
                "AgentRun workflow is already registered on this adapter."
            )

        workflow = AgentRunWorkflow(
            executor or UnwiredAgentRunExecutor(),
            compute_cleanup=compute_cleanup,
            failure_handler=failure_handler,
        )

        async def execute_agent_run(
            params: dict[str, Any],
            task_context: AsyncTaskContext,
        ) -> dict[str, Any]:
            return await workflow.execute(params, task_context)

        self._runtime.register_task(
            name=AGENT_RUN_WORKFLOW,
            handler=execute_agent_run,
            max_attempts=self._config.max_attempts,
            cancellation=self._config.cancellation_policy(),
        )

        self._registration = AgentRunRegistrationHealth(
            registered=True,
            workflow_name=AGENT_RUN_WORKFLOW,
            queue_name=self._config.queue_name,
            max_attempts=self._config.max_attempts,
            has_automatic_timeout=any(
                value is not None
                for value in self._config.cancellation_policy().values()
            ),
        )
        return self._registration

    def registration_health(self) -> AgentRunRegistrationHealth:
        return self._registration or AgentRunRegistrationHealth(
            registered=False,
            workflow_name=AGENT_RUN_WORKFLOW,
            queue_name=self._config.queue_name,
            max_attempts=self._config.max_attempts,
            has_automatic_timeout=False,
        )

    async def spawn_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> AgentRunTaskBinding:
        existing = await _load_spawnable_run(
            organization_id=organization_id,
            run_id=run_id,
        )
        if existing is not None:
            return AgentRunTaskBinding(
                organization_id=organization_id,
                run_id=run_id,
                task_id=existing,
                created=False,
            )

        task_id = await self._runtime.spawn_task(
            name=AGENT_RUN_WORKFLOW,
            params={
                "organization_id": str(organization_id),
                "run_id": str(run_id),
            },
            idempotency_key=f"agent-run:v1:{organization_id}:{run_id}",
            max_attempts=self._config.max_attempts,
        )

        created, cancellation_pending = await _bind_task(
            organization_id=organization_id,
            run_id=run_id,
            task_id=task_id,
        )
        if cancellation_pending:
            await self.cancel_task(task_id=task_id)
        return AgentRunTaskBinding(
            organization_id=organization_id,
            run_id=run_id,
            task_id=task_id,
            created=created,
        )

    async def cancel_task(self, *, task_id: UUID) -> None:
        await self._runtime.cancel_task(task_id)

    async def task_state(self, *, task_id: UUID) -> str | None:
        return await self._runtime.task_state(task_id)

    async def emit_event(self, *, event_name: str, payload: dict) -> None:
        """Wake one named durable wait; Absurd keeps the first event payload."""
        await self._runtime.emit_event(event_name=event_name, payload=payload)

    async def start_worker(self, *, worker_id: str) -> None:
        if not worker_id.strip():
            raise AgentRunRuntimeConfigurationError(
                "AgentRun worker ID must be explicit."
            )
        if self._registration is None:
            raise AgentRunRuntimeConfigurationError(
                "AgentRun workflow must be registered before worker start."
            )
        await self._runtime.start_worker(worker_id=worker_id)

    def stop_worker(self) -> None:
        self._runtime.stop_worker()

    async def close(self) -> None:
        if self._owns_runtime:
            await self._runtime.close()


async def spawn_agent_run(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> AgentRunTaskBinding:
    """Bind one product run while containing the short-lived producer client."""
    adapter = AgentRunAbsurdAdapter()
    try:
        return await adapter.spawn_run(
            organization_id=organization_id,
            run_id=run_id,
        )
    finally:
        await adapter.close()


async def emit_agent_run_event(*, event_name: str, payload: dict) -> None:
    """Deliver an already-committed product response to the durable engine."""
    adapter = AgentRunAbsurdAdapter()
    try:
        await adapter.emit_event(event_name=event_name, payload=payload)
    finally:
        await adapter.close()


async def cancel_bound_agent_run(
    *,
    organization_id: UUID,
    run_id: UUID,
    task_id: UUID,
) -> None:
    """Deliver already-committed product cancellation to Absurd."""
    adapter = AgentRunAbsurdAdapter()
    try:
        state = await adapter.task_state(task_id=task_id)
        await adapter.cancel_task(task_id=task_id)
        if state in {
            "pending",
            "sleeping",
            "cancelled",
        }:
            from eylo.modules.agent_runs.service import (
                accept_agent_run_cancellation,
            )

            await accept_agent_run_cancellation(
                organization_id=organization_id,
                run_id=run_id,
            )
    finally:
        await adapter.close()


async def _load_spawnable_run(
    *,
    organization_id: UUID,
    run_id: UUID,
) -> UUID | None:
    async with start_transaction(ro=True) as session:
        run = await AgentRunRepository(session).get(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            raise AgentRunSpawnConflict("AgentRun is unavailable for durable spawn.")
        if run.absurd_task_id is not None:
            return run.absurd_task_id
        if run.lifecycle is not AgentRunLifecycle.QUEUED:
            raise AgentRunSpawnConflict(
                f"A {run.lifecycle.value} AgentRun cannot be spawned."
            )
        return None


async def _bind_task(
    *,
    organization_id: UUID,
    run_id: UUID,
    task_id: UUID,
) -> tuple[bool, bool]:
    async with start_transaction() as session:
        run = await AgentRunRepository(session).get(
            organization_id=organization_id,
            run_id=run_id,
            for_update=True,
        )
        if run is None:
            raise AgentRunSpawnConflict("AgentRun disappeared during durable spawn.")
        if run.absurd_task_id is not None:
            if run.absurd_task_id != task_id:
                raise AgentRunSpawnConflict(
                    "AgentRun is already bound to a different durable task."
                )
            return False, run.cancellation_requested_at is not None

        run.absurd_task_id = task_id
        run.state_revision += 1
        await session.flush()
        return True, run.cancellation_requested_at is not None


__all__ = [
    "AGENT_RUN_QUEUE",
    "AGENT_RUN_WORKFLOW",
    "AbsurdRuntimeConfig",
    "AgentRunAbsurdAdapter",
    "AgentRunRegistrationHealth",
    "AgentRunRuntimeConfigurationError",
    "AgentRunSpawnConflict",
    "AgentRunTaskBinding",
    "cancel_bound_agent_run",
    "emit_agent_run_event",
    "spawn_agent_run",
]
