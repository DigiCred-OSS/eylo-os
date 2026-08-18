"""Schemas for parallel task execution.

TaskContent and TaskResultContent are stored as JSON inside SystemMessageContent.content.
Status tracking uses the message row's request_status field — content is immutable.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from eylo.common.contracts.background_task import TaskContent as TaskContent
from eylo.common.contracts.background_task import (
    TaskResultContent as TaskResultContent,
)


class WorkerResult(BaseModel):
    """Structured return value from task workers.

    Carries the result text alongside metadata about the execution.
    """

    text: str
    model_used: str
    iterations_used: int = 1
    outcome: Literal["completed", "skipped"] = Field(
        "completed",
        description=(
            "`skipped` means the worker picked the task up and decided no work "
            "was needed. It maps to RequestStatus.SKIPPED and is not a failure "
            "— the dispatcher never deduplicates, so a redundant task is an "
            "expected outcome rather than an error."
        ),
    )


class SpawnTaskFnfInput(BaseModel):
    """Input schema for the spawn_task_fnf system tool.

    NOTE: Anthropic/Bedrock reject top-level oneOf/allOf/anyOf.
    Keep schema flat.
    """

    instruction: str = Field(
        ...,
        description=(
            "Self-contained task description. Include ALL context "
            "the worker needs — it has no access to conversation history."
        ),
        max_length=4000,
    )
    swarm_id: Optional[str] = Field(
        None,
        description=(
            "Slug of the target member in the task's pinned swarm topology. "
            "Null for a bare LLM call with no tools."
        ),
    )


class SpawnTaskFnfResult(BaseModel):
    """Structured response returned by spawn_task_fnf to the LLM."""

    task_id: str = Field(..., description="ID of the created TASK message")
    status: str = Field(default="dispatched")
    instruction: str = Field(..., description="Echo of the task instruction")
    swarm_id: Optional[str] = None
    error: Optional[str] = None
