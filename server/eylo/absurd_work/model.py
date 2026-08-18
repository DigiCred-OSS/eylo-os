"""Product lifecycle projected from execution by an exact Absurd task."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

DEFAULT_MAX_ATTEMPTS = 3


class DurableState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {DurableState.SUCCEEDED, DurableState.FAILED, DurableState.CANCELLED}
)


class AbsurdBoundWorkMixin:
    """Product columns for work whose execution authority is Absurd.

    These columns project user-visible state only. No worker identity, claim,
    lease, or retry schedule exists on the product row; those belong to Absurd.
    """

    __durable_enum_name__: str = "durable_state_enum"

    @declared_attr
    def state(cls) -> Mapped[DurableState]:
        return mapped_column(
            ENUM(
                DurableState,
                name=cls.__durable_enum_name__,
                values_callable=lambda enum: [member.value for member in enum],
                create_type=False,
            ),
            nullable=False,
            default=DurableState.PENDING,
            server_default=DurableState.PENDING.value,
            index=True,
        )

    @declared_attr
    def absurd_task_id(cls):
        return mapped_column(UUID(as_uuid=True), nullable=True, unique=True)

    @declared_attr
    def attempts(cls) -> Mapped[int]:
        return mapped_column(Integer, nullable=False, server_default="0")

    @declared_attr
    def max_attempts(cls) -> Mapped[int]:
        return mapped_column(Integer, nullable=False)

    @declared_attr
    def started_at(cls):
        return mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def finished_at(cls):
        return mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def last_error(cls) -> Mapped[str | None]:
        return mapped_column(Text, nullable=True)
