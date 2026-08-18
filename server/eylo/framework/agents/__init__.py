"""Eylo-native LLM framework primitives.

This package defines contracts for the framework execution path.
"""

from .agent import AgentSpec
from .approval import (
    ApprovalActionKind,
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalRequestStatus,
    RiskLevel,
)
from .config import RunConfig
from .context import RunContext, RunInput, RunMessage
from .durable import (
    DurableInterruption,
    DurableRun,
    DurableRunKind,
    DurableRunStatus,
    InputRequest,
    InputRequestStatus,
    ProgressUpdate,
    RunCheckpoint,
)
from .errors import (
    ApprovalRequiredError,
    FrameworkError,
    GuardrailTripwireError,
    MaxTurnsExceededError,
    RunTimeoutError,
    SandboxPolicyError,
)
from .feature import (
    FeatureAgentBinding,
    FeatureArtifact,
    FeatureArtifactKind,
    FeatureSignal,
    FeatureSignalKind,
)
from .guardrail import (
    Guardrail,
    GuardrailResult,
    GuardrailSpec,
    GuardrailStage,
)
from .handoff import HandoffResult, HandoffSpec
from .hooks import RunHooks
from .items import RunItem, RunItemKind
from .model import (
    Model,
    ModelBlockKind,
    ModelOutputBlock,
    ModelResponse,
    ModelSettings,
    ModelUsage,
)
from .result import RunResult, RunStatus
from .runner import FrameworkRunner
from .sandbox import (
    SandboxActionDecision,
    SandboxArtifact,
    SandboxArtifactKind,
    SandboxNetworkPolicy,
    SandboxPolicy,
    SandboxRuntimeKind,
    SandboxSession,
    SandboxSessionStatus,
    SandboxSpec,
)
from .sandbox_runtime import (
    SANDBOX_EXEC_TOOL,
    SANDBOX_LIST_ARTIFACTS_TOOL,
    SANDBOX_READ_FILE_TOOL,
    SANDBOX_WRITE_FILE_TOOL,
    LocalWorkspaceSandboxProvider,
    SandboxActionResult,
    SandboxActionStatus,
    SandboxCommand,
    SandboxCommandResult,
    SandboxController,
    SandboxFileWrite,
    SandboxProvider,
    SandboxToolExecutor,
    sandbox_tool_specs,
)
from .session import Session, SessionSnapshot
from .tool import (
    ToolCall,
    ToolExecutionMode,
    ToolExecutor,
    ToolKind,
    ToolResult,
    ToolSpec,
)

__all__ = [
    "AgentSpec",
    "ApprovalActionKind",
    "ApprovalDecision",
    "ApprovalDecisionKind",
    "ApprovalRequest",
    "ApprovalRequestStatus",
    "ApprovalRequiredError",
    "DurableInterruption",
    "DurableRun",
    "DurableRunKind",
    "DurableRunStatus",
    "FeatureAgentBinding",
    "FeatureArtifact",
    "FeatureArtifactKind",
    "FeatureSignal",
    "FeatureSignalKind",
    "FrameworkError",
    "FrameworkRunner",
    "Guardrail",
    "GuardrailResult",
    "GuardrailSpec",
    "GuardrailStage",
    "GuardrailTripwireError",
    "HandoffResult",
    "HandoffSpec",
    "InputRequest",
    "InputRequestStatus",
    "MaxTurnsExceededError",
    "Model",
    "ModelBlockKind",
    "ModelOutputBlock",
    "ModelResponse",
    "ModelSettings",
    "ModelUsage",
    "ProgressUpdate",
    "RiskLevel",
    "RunCheckpoint",
    "RunConfig",
    "RunContext",
    "RunHooks",
    "RunInput",
    "RunItem",
    "RunItemKind",
    "RunMessage",
    "RunResult",
    "RunStatus",
    "RunTimeoutError",
    "SANDBOX_EXEC_TOOL",
    "SANDBOX_LIST_ARTIFACTS_TOOL",
    "SANDBOX_READ_FILE_TOOL",
    "SANDBOX_WRITE_FILE_TOOL",
    "SandboxActionDecision",
    "SandboxActionResult",
    "SandboxActionStatus",
    "SandboxArtifact",
    "SandboxArtifactKind",
    "SandboxCommand",
    "SandboxCommandResult",
    "SandboxController",
    "SandboxFileWrite",
    "SandboxNetworkPolicy",
    "SandboxPolicy",
    "SandboxPolicyError",
    "SandboxProvider",
    "SandboxRuntimeKind",
    "SandboxSession",
    "SandboxSessionStatus",
    "SandboxSpec",
    "SandboxToolExecutor",
    "LocalWorkspaceSandboxProvider",
    "Session",
    "SessionSnapshot",
    "ToolCall",
    "ToolExecutionMode",
    "ToolExecutor",
    "ToolKind",
    "ToolResult",
    "ToolSpec",
    "sandbox_tool_specs",
]
