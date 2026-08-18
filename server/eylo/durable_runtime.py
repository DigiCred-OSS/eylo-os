"""One explicit Absurd runtime shared by every durable platform workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast
from uuid import UUID

from absurd_sdk import (
    AsyncAbsurd,
    AsyncTaskContext,
    CancellationPolicy,
    RetryStrategy,
)
from sqlalchemy.engine import make_url

from eylo.common.config import settings

DURABLE_QUEUE = "eylo-agent-runs-v1"
DURABLE_MAX_ATTEMPTS = 3
DURABLE_RETRY_STRATEGY: RetryStrategy = {
    "kind": "exponential",
    "base_seconds": 1.0,
    "factor": 2.0,
    "max_seconds": 30.0,
}
# Explicit JSON nulls disable both automatic limits. Product state owns waits
# and cancellation policy; the engine must not invent a wall-clock deadline.
DURABLE_CANCELLATION_POLICY = cast(
    CancellationPolicy,
    {"max_duration": None, "max_delay": None},
)
DURABLE_CLAIM_TIMEOUT_SECONDS = 120
DURABLE_WORKER_CONCURRENCY = 4
DURABLE_WORKER_BATCH_SIZE = 4
DURABLE_POLL_INTERVAL_SECONDS = 0.25

DurableTaskHandler = Callable[
    [dict[str, Any], AsyncTaskContext],
    Awaitable[dict[str, Any]],
]
T = TypeVar("T")


class DurableRuntimeConfigurationError(Exception):
    """Required PostgreSQL/Absurd wiring is absent or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class AbsurdRuntimeConfig:
    """Every engine and worker option; no SDK default participates."""

    database_url: str = field(repr=False)
    queue_name: str = DURABLE_QUEUE
    max_attempts: int = DURABLE_MAX_ATTEMPTS
    claim_timeout_seconds: int = DURABLE_CLAIM_TIMEOUT_SECONDS
    worker_concurrency: int = DURABLE_WORKER_CONCURRENCY
    worker_batch_size: int = DURABLE_WORKER_BATCH_SIZE
    poll_interval_seconds: float = DURABLE_POLL_INTERVAL_SECONDS

    def __post_init__(self) -> None:
        try:
            url = make_url(self.database_url)
        except Exception as error:
            raise DurableRuntimeConfigurationError(
                "Durable execution database URL is invalid."
            ) from error
        if url.get_backend_name() != "postgresql":
            raise DurableRuntimeConfigurationError(
                "Durable execution requires PostgreSQL."
            )
        if self.queue_name != DURABLE_QUEUE:
            raise DurableRuntimeConfigurationError(
                f"Durable execution queue must be {DURABLE_QUEUE}."
            )
        numeric_options = (
            self.max_attempts,
            self.claim_timeout_seconds,
            self.worker_concurrency,
            self.worker_batch_size,
            self.poll_interval_seconds,
        )
        if any(value <= 0 for value in numeric_options):
            raise DurableRuntimeConfigurationError(
                "Durable worker options must be positive."
            )
        if self.worker_batch_size < self.worker_concurrency:
            raise DurableRuntimeConfigurationError(
                "Durable worker batch size cannot be below concurrency."
            )

    @classmethod
    def from_platform_settings(cls) -> AbsurdRuntimeConfig:
        """Use Eylo's required PostgreSQL DB with Absurd's sync driver URL."""
        try:
            platform_url = make_url(settings.DATABASE_URL)
            absurd_url = platform_url.set(drivername="postgresql").render_as_string(
                hide_password=False
            )
        except Exception as error:
            raise DurableRuntimeConfigurationError(
                "Durable execution database wiring is unavailable."
            ) from error
        return cls(database_url=absurd_url)

    def retry_strategy(self) -> RetryStrategy:
        return dict(DURABLE_RETRY_STRATEGY)  # type: ignore[return-value]

    def cancellation_policy(self) -> CancellationPolicy:
        return dict(DURABLE_CANCELLATION_POLICY)  # type: ignore[return-value]


class PlatformDurableRuntime:
    """Own one DB client, task registry and worker for all durable work kinds."""

    def __init__(self, config: AbsurdRuntimeConfig | None = None) -> None:
        self.config = config or AbsurdRuntimeConfig.from_platform_settings()
        self._app = AsyncAbsurd(
            self.config.database_url,
            queue_name=self.config.queue_name,
            default_max_attempts=self.config.max_attempts,
        )
        self._registered_names: set[str] = set()

    def register_task(
        self,
        *,
        name: str,
        handler: DurableTaskHandler,
        max_attempts: int | None = None,
        cancellation: CancellationPolicy | None = None,
    ) -> None:
        """Register one named workflow once on this shared runtime."""
        name = name.strip()
        if not name:
            raise DurableRuntimeConfigurationError(
                "Durable workflow name must be explicit."
            )
        if name in self._registered_names:
            raise DurableRuntimeConfigurationError(
                f"Durable workflow {name} is already registered."
            )
        attempts = max_attempts or self.config.max_attempts
        if attempts < 1:
            raise DurableRuntimeConfigurationError(
                "Durable workflow attempts must be positive."
            )
        decorator = self._app.register_task(
            name,
            queue=self.config.queue_name,
            default_max_attempts=attempts,
            default_cancellation=cancellation or self.config.cancellation_policy(),
        )
        decorator(handler)
        self._registered_names.add(name)

    def is_registered(self, name: str) -> bool:
        return name in self._registered_names

    async def spawn_task(
        self,
        *,
        name: str,
        params: dict[str, Any],
        idempotency_key: str,
        max_attempts: int | None = None,
    ) -> UUID:
        """Spawn one IDs-only product workflow under explicit retry policy."""
        if not name.strip() or not idempotency_key.strip():
            raise DurableRuntimeConfigurationError(
                "Durable workflow name and idempotency key must be explicit."
            )
        spawn = await self._app.spawn(
            name,
            params,
            max_attempts=max_attempts or self.config.max_attempts,
            retry_strategy=self.config.retry_strategy(),
            headers={},
            queue=self.config.queue_name,
            cancellation=self.config.cancellation_policy(),
            idempotency_key=idempotency_key,
        )
        try:
            return UUID(str(spawn["task_id"]))
        except (KeyError, TypeError, ValueError) as error:
            raise DurableRuntimeConfigurationError(
                "Absurd returned an invalid task identifier."
            ) from error

    async def cancel_task(self, task_id: UUID) -> None:
        await self._app.cancel_task(
            str(task_id),
            queue_name=self.config.queue_name,
        )

    async def task_state(self, task_id: UUID) -> str | None:
        snapshot = await self._app.fetch_task_result(
            str(task_id),
            queue_name=self.config.queue_name,
        )
        return None if snapshot is None else snapshot.state

    async def emit_event(self, *, event_name: str, payload: dict) -> None:
        await self._app.emit_event(
            event_name,
            payload,
            queue_name=self.config.queue_name,
        )

    async def start_worker(self, *, worker_id: str) -> None:
        if not worker_id.strip():
            raise DurableRuntimeConfigurationError(
                "Durable worker ID must be explicit."
            )
        if not self._registered_names:
            raise DurableRuntimeConfigurationError(
                "At least one durable workflow must be registered before worker start."
            )
        await self._app.start_worker(
            worker_id=worker_id,
            claim_timeout=self.config.claim_timeout_seconds,
            concurrency=self.config.worker_concurrency,
            batch_size=self.config.worker_batch_size,
            poll_interval=self.config.poll_interval_seconds,
        )

    def stop_worker(self) -> None:
        self._app.stop_worker()

    async def close(self) -> None:
        await self._app.close()


async def run_with_durable_heartbeat(
    context: AsyncTaskContext,
    operation: Callable[[], Awaitable[T]],
    *,
    heartbeat_seconds: int = DURABLE_CLAIM_TIMEOUT_SECONDS,
    interval_seconds: int = 30,
) -> T:
    """Keep an Absurd claim live around one long external operation."""
    if heartbeat_seconds < 1 or interval_seconds < 1:
        raise ValueError("Durable heartbeat values must be positive.")
    task = asyncio.create_task(operation())
    try:
        while not task.done():
            await context.heartbeat(seconds=heartbeat_seconds)
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=interval_seconds,
                )
            except TimeoutError:
                continue
        return await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


__all__ = [
    "AbsurdRuntimeConfig",
    "DURABLE_CANCELLATION_POLICY",
    "DURABLE_MAX_ATTEMPTS",
    "DURABLE_QUEUE",
    "DURABLE_RETRY_STRATEGY",
    "DurableRuntimeConfigurationError",
    "DurableTaskHandler",
    "PlatformDurableRuntime",
    "run_with_durable_heartbeat",
]
