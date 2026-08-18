"""Trusted harness controls for sandboxed framework work.

This module keeps the agent harness separate from sandbox compute. The trusted
server side owns policy, approvals, secrets, and orchestration; sandbox providers
only receive scoped filesystem and command operations.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import shutil
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .approval import ApprovalActionKind, ApprovalRequest, RiskLevel
from .common import FrozenFrameworkModel, JsonObject
from .context import RunContext
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
from .tool import ToolCall, ToolExecutor, ToolKind, ToolResult, ToolSpec

SANDBOX_EXEC_TOOL = "sandbox_exec"
SANDBOX_READ_FILE_TOOL = "sandbox_read_file"
SANDBOX_WRITE_FILE_TOOL = "sandbox_write_file"
SANDBOX_LIST_ARTIFACTS_TOOL = "sandbox_list_artifacts"
_SAFE_APPROVAL_EXECUTABLE = re.compile(r"[A-Za-z0-9._+-]{1,128}")
_SAFE_APPROVAL_PATH = re.compile(r"[^\x00-\x1f\x7f]{1,512}")


class SandboxActionStatus(str, Enum):
    """Outcome of one harness-controlled sandbox action."""

    COMPLETED = "completed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


class SandboxCommand(FrozenFrameworkModel):
    """Command request passed from the trusted harness to a sandbox provider."""

    argv: tuple[str, ...]
    working_directory: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)
    metadata: JsonObject = Field(default_factory=dict)


class SandboxCommandResult(FrozenFrameworkModel):
    """Captured result of a sandbox command."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        """Return whether the command exited successfully."""
        return self.exit_code == 0 and not self.timed_out


class SandboxFileWrite(FrozenFrameworkModel):
    """File write request scoped to a sandbox workspace."""

    path: str
    content: str
    metadata: JsonObject = Field(default_factory=dict)


class SandboxActionResult(FrozenFrameworkModel):
    """Structured outcome for policy-gated sandbox actions."""

    status: SandboxActionStatus
    action_kind: ApprovalActionKind
    command_result: SandboxCommandResult | None = None
    artifact: SandboxArtifact | None = None
    approval_request: ApprovalRequest | None = None
    error_message: str | None = None


class SandboxProvider(Protocol):
    """Runtime provider controlled by the trusted harness."""

    def validate_spec(self, spec: SandboxSpec) -> None:
        """Raise when this provider cannot honestly honor a sandbox spec."""

    async def create_session(self, spec: SandboxSpec) -> SandboxSession:
        """Create a sandbox session for the given spec."""

    async def execute_command(
        self,
        session: SandboxSession,
        command: SandboxCommand,
    ) -> SandboxCommandResult:
        """Execute a command inside an existing sandbox session."""

    async def read_file(self, session: SandboxSession, path: str) -> str:
        """Read a text file from the sandbox workspace."""

    async def write_file(
        self,
        session: SandboxSession,
        write: SandboxFileWrite,
    ) -> SandboxArtifact:
        """Write a text file into the sandbox workspace and return an artifact."""

    async def list_artifacts(
        self,
        session: SandboxSession,
    ) -> tuple[SandboxArtifact, ...]:
        """Return artifacts produced in the sandbox."""

    async def destroy_session(self, session: SandboxSession) -> SandboxSession:
        """Destroy a sandbox session and release runtime resources."""


class SandboxController:
    """Policy-gated facade between framework tools and sandbox providers."""

    def __init__(
        self,
        provider: SandboxProvider,
        policy: SandboxPolicy,
        *,
        durable_run_id: UUID | None = None,
        requested_by_agent_id: UUID | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._durable_run_id = durable_run_id
        self._requested_by_agent_id = requested_by_agent_id
        self._artifacts: dict[UUID, list[SandboxArtifact]] = {}

    async def create_session(self, spec: SandboxSpec) -> SandboxSession:
        """Create a provider session.

        Session creation is not policy-gated because policy applies to concrete
        actions performed inside the session.
        """
        self._provider.validate_spec(spec)
        return await self._provider.create_session(spec)

    async def execute_command(
        self,
        session: SandboxSession,
        command: SandboxCommand,
    ) -> SandboxActionResult:
        """Execute a command if sandbox policy allows it."""
        redacted_payload = _sandbox_command_approval_payload(command)
        policy_result = self._apply_policy(
            ApprovalActionKind.SANDBOX_COMMAND,
            summary=(
                "Run sandbox command "
                f"'{redacted_payload['executable']}' with "
                f"{redacted_payload['argument_count']} argument(s)."
            ),
            redacted_payload=redacted_payload,
        )
        if policy_result is not None:
            return policy_result

        result = await self._provider.execute_command(session, command)
        artifact = SandboxArtifact(
            sandbox_session_id=session.id,
            kind=SandboxArtifactKind.LOG,
            name="command-output.log",
            content_preview=_preview_command_result(result),
            metadata={
                "argv": list(command.argv),
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
            },
        )
        self._artifacts.setdefault(session.id, []).append(artifact)
        return SandboxActionResult(
            status=SandboxActionStatus.COMPLETED,
            action_kind=ApprovalActionKind.SANDBOX_COMMAND,
            command_result=result,
            artifact=artifact,
        )

    async def write_file(
        self,
        session: SandboxSession,
        write: SandboxFileWrite,
    ) -> SandboxActionResult:
        """Write a sandbox file if policy allows file writes."""
        redacted_payload = _sandbox_file_approval_payload(write)
        policy_result = self._apply_policy(
            ApprovalActionKind.FILE_WRITE,
            summary=(
                f"Write sandbox file '{redacted_payload['path']}' "
                f"({redacted_payload['content_bytes']} bytes)."
            ),
            redacted_payload=redacted_payload,
        )
        if policy_result is not None:
            return policy_result

        artifact = await self._provider.write_file(session, write)
        return SandboxActionResult(
            status=SandboxActionStatus.COMPLETED,
            action_kind=ApprovalActionKind.FILE_WRITE,
            artifact=artifact,
        )

    async def read_file(self, session: SandboxSession, path: str) -> str:
        """Read a sandbox file.

        Reads are safe by default because providers must keep paths scoped to the
        sandbox workspace.
        """
        return await self._provider.read_file(session, path)

    async def list_artifacts(
        self,
        session: SandboxSession,
    ) -> tuple[SandboxArtifact, ...]:
        """Return artifacts tracked by the provider."""
        provider_artifacts = await self._provider.list_artifacts(session)
        controller_artifacts = tuple(self._artifacts.get(session.id, ()))
        return provider_artifacts + controller_artifacts

    async def destroy_session(self, session: SandboxSession) -> SandboxSession:
        """Destroy a provider session and clean up controller artifacts."""
        self._artifacts.pop(session.id, None)
        return await self._provider.destroy_session(session)

    def _apply_policy(
        self,
        action_kind: ApprovalActionKind,
        *,
        summary: str,
        redacted_payload: JsonObject,
    ) -> SandboxActionResult | None:
        decision = self._policy.decision_for(action_kind)
        if decision == SandboxActionDecision.ALLOW:
            return None
        if decision == SandboxActionDecision.DENY:
            return SandboxActionResult(
                status=SandboxActionStatus.DENIED,
                action_kind=action_kind,
                error_message=f"Sandbox policy denied {action_kind.value}.",
            )
        if self._durable_run_id is None:
            return SandboxActionResult(
                status=SandboxActionStatus.DENIED,
                action_kind=action_kind,
                error_message=(
                    "Sandbox action requires approval but no durable_run_id "
                    "is configured."
                ),
            )
        return SandboxActionResult(
            status=SandboxActionStatus.REQUIRES_APPROVAL,
            action_kind=action_kind,
            approval_request=ApprovalRequest(
                durable_run_id=self._durable_run_id,
                requested_by_agent_id=self._requested_by_agent_id,
                action_kind=action_kind,
                action_summary=summary,
                action_payload_redacted=redacted_payload,
                risk_level=RiskLevel.MEDIUM,
                policy_reason=f"Sandbox policy requires approval for {action_kind.value}.",
            ),
        )


def _sandbox_command_approval_payload(command: SandboxCommand) -> JsonObject:
    """Describe command shape without retaining arguments or shell text."""
    executable = command.argv[0] if command.argv else ""
    if not _SAFE_APPROVAL_EXECUTABLE.fullmatch(executable):
        executable = "[redacted]"
    return {
        "executable": executable,
        "argument_count": max(len(command.argv) - 1, 0),
    }


def _sandbox_file_approval_payload(write: SandboxFileWrite) -> JsonObject:
    """Describe a file write without retaining its content."""
    path = write.path if _SAFE_APPROVAL_PATH.fullmatch(write.path) else "[redacted]"
    return {
        "path": path,
        "content_bytes": len(write.content.encode("utf-8")),
    }


class SandboxToolExecutor(ToolExecutor):
    """Expose sandbox actions as framework tools for agent-controlled environments."""

    def __init__(
        self,
        controller: SandboxController,
        session: SandboxSession,
    ) -> None:
        self._controller = controller
        self._session = session

    async def execute(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> ToolResult:
        """Execute one sandbox tool call through the trusted controller."""
        try:
            if call.name == SANDBOX_EXEC_TOOL:
                return await self._execute_command(call)
            if call.name == SANDBOX_WRITE_FILE_TOOL:
                return await self._write_file(call)
            if call.name == SANDBOX_READ_FILE_TOOL:
                return await self._read_file(call)
            if call.name == SANDBOX_LIST_ARTIFACTS_TOOL:
                return await self._list_artifacts(call)
        except (FileNotFoundError, OSError, ValueError):
            return ToolResult(
                tool_call_id=call.id,
                content="Error: Sandbox action failed.",
                is_error=True,
                metadata={"sandbox_action_failed": True},
            )

        return ToolResult(
            tool_call_id=call.id,
            content="Error: Sandbox tool is not available.",
            is_error=True,
            metadata={"sandbox_tool_unknown": True},
        )

    async def _execute_command(self, call: ToolCall) -> ToolResult:
        command = SandboxCommand(
            argv=_extract_argv(call.arguments),
            working_directory=_optional_str(call.arguments.get("working_directory")),
            timeout_seconds=_optional_float(
                call.arguments.get("timeout_seconds"),
                default=60.0,
            ),
        )
        result = await self._controller.execute_command(self._session, command)
        return _tool_result_from_action(call, result)

    async def _write_file(self, call: ToolCall) -> ToolResult:
        path = _required_str(call.arguments.get("path"), "path")
        content = _required_str(call.arguments.get("content"), "content")
        result = await self._controller.write_file(
            self._session,
            SandboxFileWrite(path=path, content=content),
        )
        return _tool_result_from_action(call, result)

    async def _read_file(self, call: ToolCall) -> ToolResult:
        path = _required_str(call.arguments.get("path"), "path")
        content = await self._controller.read_file(self._session, path)
        return ToolResult(
            tool_call_id=call.id,
            content=content,
        )

    async def _list_artifacts(self, call: ToolCall) -> ToolResult:
        artifacts = await self._controller.list_artifacts(self._session)
        return ToolResult(
            tool_call_id=call.id,
            content=json.dumps(
                [artifact.model_dump(mode="json") for artifact in artifacts]
            ),
        )


def sandbox_tool_specs() -> tuple[ToolSpec, ...]:
    """Return model-facing sandbox tools for controlled environment access."""
    return (
        ToolSpec(
            name=SANDBOX_EXEC_TOOL,
            description=(
                "Execute a non-shell command inside the sandbox. Prefer argv, "
                "for example ['date'], ['ls', '-la'], ['whoami'], or "
                "['lsb_release', '-a']."
            ),
            kind=ToolKind.SANDBOX,
            input_schema={
                "type": "object",
                "properties": {
                    "argv": {"type": "array", "items": {"type": "string"}},
                    "command": {"type": "string"},
                    "working_directory": {"type": "string"},
                    "timeout_seconds": {"type": "number"},
                },
                "anyOf": [
                    {"required": ["argv"]},
                    {"required": ["command"]},
                ],
            },
        ),
        ToolSpec(
            name=SANDBOX_WRITE_FILE_TOOL,
            description="Write a text file inside the sandbox workspace.",
            kind=ToolKind.SANDBOX,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
        ToolSpec(
            name=SANDBOX_READ_FILE_TOOL,
            description="Read a text file from the sandbox workspace.",
            kind=ToolKind.SANDBOX,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        ToolSpec(
            name=SANDBOX_LIST_ARTIFACTS_TOOL,
            description="List artifacts captured from the sandbox workspace.",
            kind=ToolKind.SANDBOX,
            input_schema={"type": "object", "properties": {}},
        ),
    )


class LocalWorkspaceSandboxProvider:
    """Local filesystem sandbox provider for development and tests.

    The provider scopes every file operation to one workspace directory and runs
    commands with ``asyncio.create_subprocess_exec`` rather than a shell. It is a
    harness adapter for local development, not a production isolation boundary.
    """

    def __init__(
        self,
        base_directory: Path,
        *,
        permitted_executables: frozenset[str],
        cleanup_on_destroy: bool = True,
    ) -> None:
        self._base_directory = base_directory.resolve()
        self._permitted_executables = permitted_executables
        self._cleanup_on_destroy = cleanup_on_destroy
        self._artifacts: dict[UUID, list[SandboxArtifact]] = {}

    def validate_spec(self, spec: SandboxSpec) -> None:
        """Reject sandbox specs whose guarantees this local provider cannot make."""
        if spec.runtime != SandboxRuntimeKind.LOCAL_WORKSPACE:
            raise ValueError(
                "Local workspace provider only supports local_workspace runtime."
            )
        if spec.network_policy != SandboxNetworkPolicy.UNRESTRICTED:
            raise ValueError(
                "Local workspace provider cannot enforce sandbox network policy. "
                "Use network_policy=unrestricted for local verification or a "
                "container/remote provider for network isolation."
            )
        if spec.allowed_domains:
            raise ValueError("Local workspace provider cannot enforce allowed_domains.")

    async def create_session(self, spec: SandboxSpec) -> SandboxSession:
        """Create a local workspace directory for a sandbox session."""
        self.validate_spec(spec)
        session = SandboxSession(
            spec=spec,
            status=SandboxSessionStatus.RUNNING,
        )
        workspace = self._base_directory / str(session.id)
        workspace.mkdir(parents=True, exist_ok=False)
        self._artifacts[session.id] = []
        return session.model_copy(update={"workspace_ref": str(workspace)})

    async def execute_command(
        self,
        session: SandboxSession,
        command: SandboxCommand,
    ) -> SandboxCommandResult:
        """Execute a non-shell command inside the local workspace."""
        if not command.argv:
            raise ValueError("Sandbox command argv must not be empty.")
        self._check_permitted_executable(command.argv[0])

        workspace = _workspace_path(session)
        cwd = _resolve_workspace_path(workspace, command.working_directory or ".")
        if not cwd.is_dir():
            raise ValueError(f"Sandbox working directory does not exist: {cwd}")

        process = await asyncio.create_subprocess_exec(
            *command.argv,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=command.timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            return SandboxCommandResult(
                exit_code=process.returncode if process.returncode is not None else -1,
                stdout=stdout_bytes.decode(errors="replace"),
                stderr=stderr_bytes.decode(errors="replace"),
                timed_out=True,
            )

        return SandboxCommandResult(
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout_bytes.decode(errors="replace"),
            stderr=stderr_bytes.decode(errors="replace"),
        )

    def _check_permitted_executable(self, executable: str) -> None:
        requested_name = Path(executable).name
        if executable != requested_name:
            raise ValueError("Sandbox commands must use executable names, not paths.")
        if requested_name not in self._permitted_executables:
            raise ValueError(f"Sandbox executable is not permitted: {requested_name}")

    async def read_file(self, session: SandboxSession, path: str) -> str:
        """Read a file within the local workspace."""
        file_path = _resolve_workspace_path(_workspace_path(session), path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        return file_path.read_text(encoding="utf-8")

    async def write_file(
        self,
        session: SandboxSession,
        write: SandboxFileWrite,
    ) -> SandboxArtifact:
        """Write a file within the local workspace and track it as an artifact."""
        file_path = _resolve_workspace_path(_workspace_path(session), write.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(write.content, encoding="utf-8")

        artifact = SandboxArtifact(
            sandbox_session_id=session.id,
            kind=SandboxArtifactKind.FILE,
            name=write.path,
            uri=str(file_path),
            content_preview=write.content[:500],
            metadata=write.metadata,
        )
        self._artifacts.setdefault(session.id, []).append(artifact)
        return artifact

    async def list_artifacts(
        self,
        session: SandboxSession,
    ) -> tuple[SandboxArtifact, ...]:
        """Return artifacts written through this provider."""
        return tuple(self._artifacts.get(session.id, ()))

    async def destroy_session(self, session: SandboxSession) -> SandboxSession:
        """Remove the local workspace when configured to clean up."""
        workspace = _workspace_path(session)
        if self._cleanup_on_destroy and workspace.exists():
            shutil.rmtree(workspace)
        self._artifacts.pop(session.id, None)
        return session.model_copy(update={"status": SandboxSessionStatus.STOPPED})


def _workspace_path(session: SandboxSession) -> Path:
    if session.workspace_ref is None:
        raise ValueError("Sandbox session has no workspace_ref.")
    return Path(session.workspace_ref).resolve()


def _resolve_workspace_path(workspace: Path, path: str) -> Path:
    candidate = (workspace / path).resolve()
    if candidate != workspace and workspace not in candidate.parents:
        raise ValueError("Sandbox path escapes the workspace.")
    return candidate


def _preview_command_result(result: SandboxCommandResult) -> str:
    output = result.stdout if result.stdout else result.stderr
    return output[:500]


def _tool_result_from_action(
    call: ToolCall,
    result: SandboxActionResult,
) -> ToolResult:
    metadata = {
        "sandbox_status": result.status.value,
        "action_kind": result.action_kind.value,
    }
    if result.approval_request is not None:
        metadata["approval_request"] = result.approval_request.model_dump(mode="json")
    if result.artifact is not None:
        metadata["artifact"] = result.artifact.model_dump(mode="json")

    if result.status == SandboxActionStatus.COMPLETED:
        return ToolResult(
            tool_call_id=call.id,
            content=_completed_action_content(result),
            metadata=metadata,
        )
    return ToolResult(
        tool_call_id=call.id,
        content=result.error_message or f"Sandbox action status: {result.status.value}",
        is_error=result.status == SandboxActionStatus.DENIED,
        metadata=metadata,
    )


def _completed_action_content(result: SandboxActionResult) -> str:
    if result.command_result is not None:
        command_result = result.command_result
        if command_result.stdout:
            return command_result.stdout
        if command_result.stderr:
            return command_result.stderr
        return f"Command exited with code {command_result.exit_code}."
    if result.artifact is not None:
        return f"Sandbox artifact created: {result.artifact.name}"
    return "Sandbox action completed."


def _extract_argv(arguments: JsonObject) -> tuple[str, ...]:
    argv_value = arguments.get("argv")
    if isinstance(argv_value, list) and all(
        isinstance(item, str) for item in argv_value
    ):
        return tuple(argv_value)
    if isinstance(argv_value, tuple) and all(
        isinstance(item, str) for item in argv_value
    ):
        return argv_value

    command_value = arguments.get("command")
    if isinstance(command_value, str):
        return tuple(shlex.split(command_value))

    raise ValueError("sandbox_exec requires argv: list[str] or command: str.")


def _required_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_float(value: object, *, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, int | float):
        return float(value)
    raise ValueError("timeout_seconds must be a number.")
