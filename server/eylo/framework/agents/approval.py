"""Human approval contracts for risky framework actions."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject


class ApprovalActionKind(str, Enum):
    """Action families that may require approval."""

    TOOL_CALL = "tool_call"
    SANDBOX_COMMAND = "sandbox_command"
    NETWORK_ACCESS = "network_access"
    FILE_WRITE = "file_write"
    EXTERNAL_API_CALL = "external_api_call"
    HANDOFF = "handoff"


class RiskLevel(str, Enum):
    """Risk level assigned by policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalRequestStatus(str, Enum):
    """Lifecycle of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalDecisionKind(str, Enum):
    """Decision made by a user or admin."""

    APPROVE = "approve"
    REJECT = "reject"


class ApprovalRequest(FrozenFrameworkModel):
    """Permission request for one concrete risky action."""

    id: UUID = Field(default_factory=uuid4)
    durable_run_id: UUID
    requested_by_agent_id: UUID | None = None
    action_kind: ApprovalActionKind
    action_summary: str
    action_payload_redacted: JsonObject = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    policy_reason: str
    expires_at: str | None = None
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING
    resume_checkpoint_id: UUID | None = None
    metadata: JsonObject = Field(default_factory=dict)


class ApprovalDecision(FrozenFrameworkModel):
    """User/admin decision for an approval request."""

    approval_request_id: UUID
    decided_by: UUID | str
    decision: ApprovalDecisionKind
    comment: str | None = None
    approved_payload_override: JsonObject | None = None
