"""Durable background-run contracts."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from .approval import ApprovalRequest
from .common import FrozenFrameworkModel, JsonObject
from .sandbox import SandboxSpec


class DurableRunStatus(str, Enum):
    """Lifecycle state for long-running agents."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DurableRunKind(str, Enum):
    """Kinds of durable agent work."""

    CODING = "coding"
    ANALYTICS = "analytics"
    RESEARCH = "research"
    REPORT = "report"
    WORKFLOW = "workflow"
    FEATURE_AGENT = "feature_agent"


class DurableRun(FrozenFrameworkModel):
    """Persisted envelope for nonblocking background agent work."""

    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    conversation_id: UUID | None = None
    agent_id: UUID
    kind: DurableRunKind
    status: DurableRunStatus = DurableRunStatus.QUEUED
    parent_run_id: UUID | None = None
    sandbox: SandboxSpec | None = None
    latest_checkpoint_id: UUID | None = None
    final_artifact_ids: tuple[UUID, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)


class ProgressUpdate(FrozenFrameworkModel):
    """Lightweight status update from a durable run."""

    durable_run_id: UUID
    message: str
    percent: int | None = Field(default=None, ge=0, le=100)
    metadata: JsonObject = Field(default_factory=dict)


class InputRequestStatus(str, Enum):
    """Lifecycle state for an input request."""

    PENDING = "pending"
    ANSWERED = "answered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class InputRequest(FrozenFrameworkModel):
    """Request for missing information needed to continue a durable run."""

    id: UUID = Field(default_factory=uuid4)
    durable_run_id: UUID
    prompt: str
    expected_input_schema: JsonObject = Field(default_factory=dict)
    status: InputRequestStatus = InputRequestStatus.PENDING
    resume_checkpoint_id: UUID | None = None
    metadata: JsonObject = Field(default_factory=dict)


class RunCheckpoint(FrozenFrameworkModel):
    """Durable snapshot used to resume or inspect a background run."""

    id: UUID = Field(default_factory=uuid4)
    durable_run_id: UUID
    state: JsonObject = Field(default_factory=dict)
    summary: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class DurableInterruption(FrozenFrameworkModel):
    """One reason a durable run paused before completion."""

    durable_run_id: UUID
    input_request: InputRequest | None = None
    approval_request: ApprovalRequest | None = None
