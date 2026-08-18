"""Sandbox contracts for isolated long-running agent work."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .approval import ApprovalActionKind
from .common import FrozenFrameworkModel, JsonObject


class SandboxRuntimeKind(str, Enum):
    """Runtime backing a sandbox session."""

    LOCAL_WORKSPACE = "local_workspace"
    CONTAINER = "container"
    REMOTE_WORKER = "remote_worker"


class SandboxNetworkPolicy(str, Enum):
    """Network access policy for a sandbox."""

    BLOCKED = "blocked"
    ALLOWLIST = "allowlist"
    UNRESTRICTED = "unrestricted"


class SandboxActionDecision(str, Enum):
    """Policy decision for a proposed sandbox action."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class SandboxSpec(FrozenFrameworkModel):
    """Declarative request for isolated execution."""

    runtime: SandboxRuntimeKind = SandboxRuntimeKind.LOCAL_WORKSPACE
    network_policy: SandboxNetworkPolicy = SandboxNetworkPolicy.BLOCKED
    allowed_domains: tuple[str, ...] = ()
    max_runtime_seconds: int = Field(default=900, gt=0)
    max_storage_mb: int = Field(default=512, gt=0)
    metadata: JsonObject = Field(default_factory=dict)


class SandboxPolicy(FrozenFrameworkModel):
    """Policy for sandbox actions."""

    denied_actions: tuple[ApprovalActionKind, ...] = ()
    approval_required_actions: tuple[ApprovalActionKind, ...] = ()

    @model_validator(mode="after")
    def _no_contradictory_actions(self) -> SandboxPolicy:
        overlap = set(self.denied_actions) & set(self.approval_required_actions)
        if overlap:
            raise ValueError(
                f"Actions cannot be in both denied and approval_required: {overlap}"
            )
        return self

    def decision_for(self, action_kind: ApprovalActionKind) -> SandboxActionDecision:
        """Return the policy decision for an action kind."""
        if action_kind in self.denied_actions:
            return SandboxActionDecision.DENY
        if action_kind in self.approval_required_actions:
            return SandboxActionDecision.REQUIRE_APPROVAL
        return SandboxActionDecision.ALLOW


class SandboxSessionStatus(str, Enum):
    """Lifecycle state of a sandbox session."""

    REQUESTED = "requested"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class SandboxSession(FrozenFrameworkModel):
    """Runtime sandbox instance attached to a run."""

    id: UUID = Field(default_factory=uuid4)
    durable_run_id: UUID | None = None
    spec: SandboxSpec = Field(default_factory=SandboxSpec)
    status: SandboxSessionStatus = SandboxSessionStatus.REQUESTED
    workspace_ref: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class SandboxArtifactKind(str, Enum):
    """Artifacts produced by sandboxed execution."""

    FILE = "file"
    DIFF = "diff"
    LOG = "log"
    REPORT = "report"
    CHART = "chart"
    TEST_RESULT = "test_result"


class SandboxArtifact(FrozenFrameworkModel):
    """Typed output produced inside a sandbox."""

    id: UUID = Field(default_factory=uuid4)
    sandbox_session_id: UUID
    kind: SandboxArtifactKind
    name: str
    uri: str | None = None
    content_preview: str | None = None
    metadata: JsonObject = Field(default_factory=dict)
