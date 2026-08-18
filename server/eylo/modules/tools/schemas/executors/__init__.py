"""Public exports for the `tools` domain package."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Base class for tool execution results."""

    success: bool = Field(
        ...,
        description="Indicates whether the tool execution was successful.",
    )
    result: Optional[Any] = Field(
        None,
        description="The result of the tool execution, if successful.",
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the tool execution failed.",
    )
    tool_id: str = Field(
        ...,
        description="The ID of the tool that was executed.",
    )
    error_code: Optional[int] = Field(
        None,
        description=(
            "HTTP status behind a failure, when there was one. A code the "
            "caller can branch on, rather than only a sentence it would have "
            "to parse. Transport-level failures are already retried before "
            "this is set, so reaching a caller means retrying again is not "
            "worth it."
        ),
    )
    retryable: bool = Field(
        False,
        description=(
            "True when the failure was transient and retries were exhausted. "
            "Distinguishes 'the service is struggling' from 'this request is "
            "wrong', which need different handling."
        ),
    )
