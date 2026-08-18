"""Runner-specific exceptions.

Each exception carries structured data so the runner can build
appropriate error messages and RunResult statuses.
"""


class RunnerError(Exception):
    """Base exception for all runner errors."""

    pass


class MaxTurnsExceededError(RunnerError):
    """Raised when the run exceeds the configured max_turns."""

    def __init__(self, max_turns: int, current_turn: int):
        self.max_turns = max_turns
        self.current_turn = current_turn
        super().__init__(f"Agent exceeded maximum turns ({current_turn}/{max_turns})")


class RequestTimeoutError(RunnerError):
    """Raised when the run exceeds the configured request_timeout."""

    def __init__(self, timeout: float, elapsed: float):
        self.timeout = timeout
        self.elapsed = elapsed
        super().__init__(f"Agent request timed out ({elapsed:.1f}s / {timeout:.1f}s)")


class HandoffCircuitBreakerError(RunnerError):
    """Raised when too many handoffs occur in a short window."""

    def __init__(self, handoff_count: int, window_size: int):
        self.handoff_count = handoff_count
        self.window_size = window_size
        super().__init__(
            f"Handoff circuit breaker triggered "
            f"({handoff_count} handoffs in last {window_size} messages)"
        )


class ToolExecutionError(RunnerError):
    """Raised when a tool execution fails unrecoverably."""

    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        self.error_detail = error
        super().__init__(f"Tool '{tool_name}' failed: {error}")
