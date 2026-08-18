"""Framework-specific exceptions."""

from __future__ import annotations


class FrameworkError(Exception):
    """Base error for the new framework path."""


class MaxTurnsExceededError(FrameworkError):
    """Raised when a run exceeds its configured turn limit."""


class RunTimeoutError(FrameworkError):
    """Raised when a run exceeds its configured timeout."""


class GuardrailTripwireError(FrameworkError):
    """Raised when a guardrail blocks execution."""


class ApprovalRequiredError(FrameworkError):
    """Raised when execution must pause for human approval."""


class SandboxPolicyError(FrameworkError):
    """Raised when sandbox policy denies an action."""
