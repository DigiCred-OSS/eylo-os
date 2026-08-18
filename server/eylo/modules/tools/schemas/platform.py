"""Tool-module exports for platform-native contracts."""

from eylo.common.contracts.tool_platform import PlatformTool as PlatformTool
from eylo.common.contracts.tool_platform import (
    PlatformToolInputSchema as PlatformToolInputSchema,
)
from eylo.common.contracts.tool_platform import (
    PlatformToolResult as PlatformToolResult,
)
from eylo.common.contracts.tool_platform import PlatformToolUse as PlatformToolUse

__all__ = [
    "PlatformTool",
    "PlatformToolInputSchema",
    "PlatformToolResult",
    "PlatformToolUse",
]
