"""Content-free deletion lifecycle values and expected failures."""

from __future__ import annotations

from enum import StrEnum


class DeletionTargetType(StrEnum):
    """Lifecycle roots organizations may erase from Eylo in V1."""

    CALL = "call"
    CONTACT = "contact"


class DeletionJobStatus(StrEnum):
    """Organization-visible product state, separate from Absurd claims."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DeletionErrorCode(StrEnum):
    """Bounded diagnostics that cannot contain product or provider data."""

    CALL_ACTIVE = "call_active"
    OBJECT_DELETE_FAILED = "object_delete_failed"
    ERASURE_FAILED = "erasure_failed"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_FAILURE = "internal_failure"


class DeletionJobError(Exception):
    """Base expected deletion-job failure."""


class DeletionJobNotFound(DeletionJobError):
    """No deletion job exists inside the requesting organization."""


class DeletionTargetNotFound(DeletionJobError):
    """The target is absent from the requesting organization."""


class DeletionJobConflict(DeletionJobError):
    """A deletion lifecycle transition conflicts with durable state."""


class DeletionExecutionFailure(DeletionJobError):
    """One retry-safe, content-free execution failure."""

    def __init__(
        self,
        code: DeletionErrorCode,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.retryable = retryable


__all__ = [
    "DeletionErrorCode",
    "DeletionExecutionFailure",
    "DeletionJobConflict",
    "DeletionJobError",
    "DeletionJobNotFound",
    "DeletionJobStatus",
    "DeletionTargetNotFound",
    "DeletionTargetType",
]
