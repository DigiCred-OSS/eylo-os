"""Application services for the `tools` domain."""

from abc import ABC, abstractmethod

from eylo.modules.tools.schemas.executors import ToolResult


class ToolExecutionService(ABC):
    """Tool Execution Service."""

    def __init__(self, tool_id: str):
        """Initialize Tool Execution Service."""
        self.tool_id = tool_id

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """Execute for the "tools" domain."""
        raise NotImplementedError("Execute tool method not implemented")
