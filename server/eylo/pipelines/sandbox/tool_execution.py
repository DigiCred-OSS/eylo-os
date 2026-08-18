"""Durable AgentRun-scoped execution for published sandbox system tools.

Every call gets fresh compute, restores the latest workspace checkpoint,
performs one bounded action, stores raw model-facing output only beside the
private workspace checkpoint, then destroys compute. Absurd checkpoints carry
only a small receipt; AgentRun step/API projections carry only safe metadata.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select

from eylo.common.contracts.sandbox import SandboxError
from eylo.common.database import start_transaction
from eylo.modules.agent_runs.budgets import current_agent_run_id
from eylo.modules.agent_runs.domain import AgentRunStepKind, AgentRunStepStatus
from eylo.modules.agent_runs.models import AgentRunStepModel
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.sandbox.access import SandboxAccessError
from eylo.pipelines.outbound.durable_execution import DurableStepContext
from eylo.pipelines.sandbox.sessions import (
    acquire,
    discard_live_run_sessions,
    export_and_destroy_workspace,
    store_workspace_checkpoint_in_transaction,
    workspace_checkpoint_for_step,
)

logger = logging.getLogger(__name__)

SANDBOX_EXEC_TOOL_SLUG = "sandbox_exec"
SANDBOX_READ_TOOL_SLUG = "sandbox_read"
SANDBOX_WRITE_TOOL_SLUG = "sandbox_write"
SANDBOX_TOOL_SLUGS = frozenset(
    {
        SANDBOX_EXEC_TOOL_SLUG,
        SANDBOX_READ_TOOL_SLUG,
        SANDBOX_WRITE_TOOL_SLUG,
    }
)

_DEFAULT_TIMEOUT_SECONDS = 60
_MAX_TIMEOUT_SECONDS = 300
_MAX_COMMAND_CHARS = 2_000
_MAX_PATH_CHARS = 512
_MAX_MODEL_OUTPUT_BYTES = 4_000
_STEP_VERSION = 1


class SandboxToolActionKind(str, Enum):
    EXEC = "exec"
    READ = "read"
    WRITE = "write"


class SandboxToolInputError(ValueError):
    """The model supplied an invalid sandbox tool payload."""


@dataclass(frozen=True, slots=True)
class SandboxToolAction:
    kind: SandboxToolActionKind
    command: str | None = None
    path: str | None = None
    content: str | None = None
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_call(cls, slug: str, arguments: dict[str, Any]) -> SandboxToolAction:
        if slug == SANDBOX_EXEC_TOOL_SLUG:
            _require_fields(arguments, allowed={"command", "timeout_seconds"})
            command = _required_text(
                arguments,
                "command",
                max_chars=_MAX_COMMAND_CHARS,
            )
            timeout = arguments.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)
            if (
                isinstance(timeout, bool)
                or not isinstance(timeout, int)
                or not 1 <= timeout <= _MAX_TIMEOUT_SECONDS
            ):
                raise SandboxToolInputError(
                    "timeout_seconds must be an integer between 1 and 300."
                )
            return cls(
                kind=SandboxToolActionKind.EXEC,
                command=command,
                timeout_seconds=timeout,
            )
        if slug == SANDBOX_READ_TOOL_SLUG:
            _require_fields(arguments, allowed={"path"})
            return cls(
                kind=SandboxToolActionKind.READ,
                path=_required_text(arguments, "path", max_chars=_MAX_PATH_CHARS),
            )
        if slug == SANDBOX_WRITE_TOOL_SLUG:
            _require_fields(arguments, allowed={"path", "content"})
            return cls(
                kind=SandboxToolActionKind.WRITE,
                path=_required_text(arguments, "path", max_chars=_MAX_PATH_CHARS),
                content=_required_text(arguments, "content", allow_empty=True),
            )
        raise SandboxToolInputError("Sandbox tool is not supported.")

    @property
    def safe_intent(self) -> dict[str, Any]:
        intent: dict[str, Any] = {"action": self.kind.value}
        if self.path is not None:
            intent["path"] = self.path
        if self.command is not None:
            intent["command_sha256"] = _digest(self.command.encode("utf-8"))
        return intent


@dataclass(frozen=True, slots=True)
class SandboxToolExecutionOutcome:
    content: dict[str, Any]
    is_error: bool
    metadata: dict[str, Any]


async def execute_agent_sandbox_tool(
    *,
    tool_slug: str,
    tool_input: dict[str, Any],
    organization_id: UUID,
    agent_id: UUID,
    agent_run_id: UUID,
    tool_command_id: UUID,
    durable_context: DurableStepContext,
) -> SandboxToolExecutionOutcome:
    """Execute one published sandbox tool under the current AgentRun."""
    active_run_id = current_agent_run_id()
    if active_run_id is None or active_run_id != agent_run_id:
        return _failure_outcome(
            "durable_agent_run_required",
            message=(
                "Sandbox work requires a durable agent run and is unavailable "
                "inside the live voice path."
            ),
        )
    try:
        action = SandboxToolAction.from_call(tool_slug, tool_input)
    except SandboxToolInputError:
        return _failure_outcome(
            "sandbox_input_invalid",
            message="Sandbox tool input is invalid.",
        )

    product_step_key = f"sandbox:tool:{tool_command_id}"
    receipt = await durable_context.step(
        key=product_step_key,
        version=_STEP_VERSION,
        operation=lambda: _execute_and_project(
            organization_id=organization_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            product_step_key=product_step_key,
            action=action,
        ),
    )
    return await _outcome_from_receipt(
        organization_id=organization_id,
        agent_run_id=agent_run_id,
        product_step_key=product_step_key,
        receipt=receipt,
    )


async def _execute_and_project(
    *,
    organization_id: UUID,
    agent_id: UUID,
    agent_run_id: UUID,
    product_step_key: str,
    action: SandboxToolAction,
) -> dict[str, Any]:
    existing = await _load_step(
        organization_id=organization_id,
        agent_run_id=agent_run_id,
        step_key=product_step_key,
    )
    if existing is not None:
        return _receipt_from_step(existing)

    try:
        await discard_live_run_sessions(
            organization_id=organization_id,
            agent_run_id=agent_run_id,
        )
        adapter, session = await acquire(
            organization_id=organization_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
        )
        result, evidence, checkpointable = await _perform_action(
            adapter,
            session,
            action,
        )
        if not checkpointable:
            await discard_live_run_sessions(
                organization_id=organization_id,
                agent_run_id=agent_run_id,
            )
            return await _record_failed_step(
                organization_id=organization_id,
                agent_run_id=agent_run_id,
                step_key=product_step_key,
                action=action,
                failure_code="sandbox_command_timed_out",
                evidence=evidence,
            )

        exported = await export_and_destroy_workspace(session)
        async with start_transaction() as db:
            existing = await db.scalar(
                select(AgentRunStepModel).where(
                    AgentRunStepModel.organization_id == organization_id,
                    AgentRunStepModel.run_id == agent_run_id,
                    AgentRunStepModel.step_key == product_step_key,
                    AgentRunStepModel.deleted.is_(False),
                )
            )
            if existing is not None:
                return _receipt_from_step(existing)
            checkpoint = await store_workspace_checkpoint_in_transaction(
                db,
                organization_id=organization_id,
                source_step_key=product_step_key,
                exported=exported,
                tool_result=result,
            )
            now = datetime.now(timezone.utc)
            db.add(
                AgentRunStepModel(
                    organization_id=organization_id,
                    run_id=agent_run_id,
                    step_key=product_step_key,
                    kind=AgentRunStepKind.SANDBOX,
                    status=AgentRunStepStatus.COMPLETED,
                    intent=action.safe_intent,
                    safe_summary=_safe_summary(action, evidence),
                    evidence=evidence,
                    artifact_refs=[
                        {
                            "kind": "sandbox_workspace_checkpoint",
                            "revision": checkpoint.revision,
                            "digest": checkpoint.workspace_digest,
                        }
                    ],
                    started_at=now,
                    completed_at=now,
                )
            )
            await db.flush()
            return {
                "status": AgentRunStepStatus.COMPLETED.value,
                "checkpoint_revision": checkpoint.revision,
                "workspace_digest": checkpoint.workspace_digest,
            }
    except asyncio.CancelledError:
        await discard_live_run_sessions(
            organization_id=organization_id,
            agent_run_id=agent_run_id,
        )
        raise
    except NotConfiguredError:
        failure_code = "sandbox_not_configured"
    except SandboxAccessError:
        failure_code = "sandbox_access_denied"
    except SandboxError as error:
        logger.warning(
            "Sandbox tool action failed error_type=%s",
            type(error).__name__,
        )
        failure_code = "sandbox_execution_failed"

    await discard_live_run_sessions(
        organization_id=organization_id,
        agent_run_id=agent_run_id,
    )
    return await _record_failed_step(
        organization_id=organization_id,
        agent_run_id=agent_run_id,
        step_key=product_step_key,
        action=action,
        failure_code=failure_code,
    )


async def _perform_action(adapter, session, action: SandboxToolAction):
    if action.kind is SandboxToolActionKind.WRITE:
        assert action.path is not None and action.content is not None
        encoded = action.content.encode("utf-8")
        await adapter.write(session, action.path, encoded)
        return (
            {
                "success": True,
                "path": action.path,
                "message": f"Wrote {action.path}.",
            },
            {
                "action": action.kind.value,
                "path": action.path,
                "content_bytes": len(encoded),
                "content_sha256": _digest(encoded),
            },
            True,
        )

    if action.kind is SandboxToolActionKind.READ:
        assert action.path is not None
        raw = await adapter.read(session, action.path)
        digest = _digest(raw)
        evidence = {
            "action": action.kind.value,
            "path": action.path,
            "content_bytes": len(raw),
            "content_sha256": digest,
        }
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            evidence["text"] = False
            return (
                {
                    "success": False,
                    "content": "",
                    "message": "Sandbox file is not UTF-8 text.",
                },
                evidence,
                True,
            )
        if len(raw) > _MAX_MODEL_OUTPUT_BYTES:
            evidence["output_rejected"] = True
            return (
                {
                    "success": False,
                    "content": "",
                    "message": (
                        "Sandbox file exceeds the model-output ceiling; no "
                        "partial content was returned."
                    ),
                },
                evidence,
                True,
            )
        evidence["text"] = True
        return (
            {"success": True, "content": content, "message": ""},
            evidence,
            True,
        )

    assert action.command is not None
    execution = await adapter.exec(
        session,
        action.command,
        timeout_seconds=action.timeout_seconds,
    )
    stdout_bytes = execution.stdout.encode("utf-8")
    stderr_bytes = execution.stderr.encode("utf-8")
    evidence = {
        "action": action.kind.value,
        "command_sha256": _digest(action.command.encode("utf-8")),
        "exit_code": execution.exit_code,
        "stdout_bytes": len(stdout_bytes),
        "stdout_sha256": _digest(stdout_bytes),
        "stderr_bytes": len(stderr_bytes),
        "stderr_sha256": _digest(stderr_bytes),
        "timed_out": execution.timed_out,
    }
    if execution.timed_out:
        return (
            {
                "success": False,
                "exit_code": execution.exit_code,
                "stdout": "",
                "stderr": "",
                "timed_out": True,
                "message": "Sandbox command timed out and compute was destroyed.",
            },
            evidence,
            False,
        )
    if len(stdout_bytes) + len(stderr_bytes) > _MAX_MODEL_OUTPUT_BYTES:
        evidence["output_rejected"] = True
        return (
            {
                "success": False,
                "exit_code": execution.exit_code,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "message": (
                    "Sandbox command output exceeds the model-output ceiling; "
                    "no partial output was returned."
                ),
            },
            evidence,
            True,
        )
    return (
        {
            "success": execution.ok,
            "exit_code": execution.exit_code,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "timed_out": False,
            "message": "",
        },
        evidence,
        True,
    )


async def _record_failed_step(
    *,
    organization_id: UUID,
    agent_run_id: UUID,
    step_key: str,
    action: SandboxToolAction,
    failure_code: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_evidence = {**(evidence or {}), "failure_code": failure_code}
    async with start_transaction() as db:
        existing = await db.scalar(
            select(AgentRunStepModel).where(
                AgentRunStepModel.organization_id == organization_id,
                AgentRunStepModel.run_id == agent_run_id,
                AgentRunStepModel.step_key == step_key,
                AgentRunStepModel.deleted.is_(False),
            )
        )
        if existing is not None:
            return _receipt_from_step(existing)
        now = datetime.now(timezone.utc)
        db.add(
            AgentRunStepModel(
                organization_id=organization_id,
                run_id=agent_run_id,
                step_key=step_key,
                kind=AgentRunStepKind.SANDBOX,
                status=AgentRunStepStatus.FAILED,
                intent=action.safe_intent,
                safe_summary="Sandbox action failed without retained compute.",
                evidence=safe_evidence,
                artifact_refs=[],
                started_at=now,
                completed_at=now,
            )
        )
        await db.flush()
    return {
        "status": AgentRunStepStatus.FAILED.value,
        "failure_code": failure_code,
    }


async def _outcome_from_receipt(
    *,
    organization_id: UUID,
    agent_run_id: UUID,
    product_step_key: str,
    receipt: object,
) -> SandboxToolExecutionOutcome:
    if not isinstance(receipt, dict):
        raise SandboxError("Sandbox durable receipt is invalid.")
    status = receipt.get("status")
    if status == AgentRunStepStatus.FAILED.value:
        code = str(receipt.get("failure_code") or "sandbox_execution_failed")
        return _failure_outcome(code, message=_failure_message(code))
    if status != AgentRunStepStatus.COMPLETED.value:
        raise SandboxError("Sandbox durable receipt has an invalid status.")

    checkpoint = await workspace_checkpoint_for_step(
        organization_id=organization_id,
        agent_run_id=agent_run_id,
        source_step_key=product_step_key,
    )
    if checkpoint is None or not isinstance(checkpoint.tool_result, dict):
        raise SandboxError("Sandbox checkpoint is missing its canonical tool result.")
    content = dict(checkpoint.tool_result)
    return SandboxToolExecutionOutcome(
        content=content,
        is_error=content.get("success") is not True,
        metadata={
            "sandbox_execution": True,
            "sandbox_step_key": product_step_key,
            "sandbox_checkpoint_revision": checkpoint.revision,
            "sandbox_workspace_digest": checkpoint.workspace_digest,
        },
    )


async def _load_step(
    *,
    organization_id: UUID,
    agent_run_id: UUID,
    step_key: str,
) -> AgentRunStepModel | None:
    async with start_transaction(ro=True) as db:
        return await db.scalar(
            select(AgentRunStepModel).where(
                AgentRunStepModel.organization_id == organization_id,
                AgentRunStepModel.run_id == agent_run_id,
                AgentRunStepModel.step_key == step_key,
                AgentRunStepModel.deleted.is_(False),
            )
        )


def _receipt_from_step(step: AgentRunStepModel) -> dict[str, Any]:
    if step.status is AgentRunStepStatus.FAILED:
        evidence = step.evidence or {}
        return {
            "status": step.status.value,
            "failure_code": evidence.get("failure_code")
            or "sandbox_execution_failed",
        }
    if step.status is not AgentRunStepStatus.COMPLETED or not step.artifact_refs:
        raise SandboxError("Sandbox product step is incomplete.")
    artifact = step.artifact_refs[0]
    return {
        "status": step.status.value,
        "checkpoint_revision": artifact.get("revision"),
        "workspace_digest": artifact.get("digest"),
    }


def _safe_summary(
    action: SandboxToolAction,
    evidence: dict[str, Any],
) -> str:
    if action.kind is SandboxToolActionKind.EXEC:
        return f"Sandbox command exited with code {evidence['exit_code']}."
    return f"Sandbox {action.kind.value} completed."


def _failure_outcome(code: str, *, message: str) -> SandboxToolExecutionOutcome:
    return SandboxToolExecutionOutcome(
        content={"success": False, "error": code, "message": message},
        is_error=True,
        metadata={"sandbox_execution": True, "sandbox_failure_code": code},
    )


def _failure_message(code: str) -> str:
    return {
        "sandbox_not_configured": "No sandbox is configured for this organization.",
        "sandbox_access_denied": "Sandbox access is not granted to this agent.",
        "sandbox_command_timed_out": "Sandbox command timed out.",
    }.get(code, "Sandbox action failed.")


def _require_fields(arguments: dict[str, Any], *, allowed: set[str]) -> None:
    if set(arguments) - allowed:
        raise SandboxToolInputError("Sandbox tool input has unsupported fields.")


def _required_text(
    arguments: dict[str, Any],
    key: str,
    *,
    max_chars: int | None = None,
    allow_empty: bool = False,
) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SandboxToolInputError(f"{key} must be text.")
    if max_chars is not None and len(value) > max_chars:
        raise SandboxToolInputError(f"{key} exceeds its character ceiling.")
    return value


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "SANDBOX_TOOL_SLUGS",
    "SandboxToolExecutionOutcome",
    "execute_agent_sandbox_tool",
]
