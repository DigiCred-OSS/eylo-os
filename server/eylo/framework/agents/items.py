"""Typed item stream produced by framework runs."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from .common import FrameworkMetadata, FrozenFrameworkModel, JsonObject


class RunItemKind(str, Enum):
    """Kinds of items emitted during a run."""

    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    HANDOFF = "handoff"
    TOKEN_DELTA = "token_delta"
    PROGRESS = "progress"
    INPUT_REQUEST = "input_request"
    APPROVAL_REQUEST = "approval_request"
    SANDBOX_ARTIFACT = "sandbox_artifact"
    ERROR = "error"


class RunItem(FrozenFrameworkModel):
    """One inspectable item created during a run."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    kind: RunItemKind
    payload: JsonObject = Field(default_factory=dict)
    message: str | None = None
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)
