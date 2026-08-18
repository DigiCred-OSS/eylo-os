"""Vendor-neutral sandbox execution contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SandboxAccess(StrEnum):
    """What an agent may do with a sandbox.

    V1 exposes only bounded no-egress compute. A networked value would be a
    promise that the Docker adapter cannot enforce safely.
    """

    RUN = "run"


class SandboxState(StrEnum):
    """Where a session is in its life."""

    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    DESTROYED = "destroyed"


class SandboxManifest(BaseModel):
    """What a session starts as.

    Every field that widens what the sandbox can do is **opt-in and named**.
    The defaults are the restrictive ones, because the code that will run here
    was written by a model that has been reading untrusted documents.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    image: str = Field(min_length=1)
    files: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    network: bool
    allowed_hosts: list[str] = Field(default_factory=list)
    memory_mb: int = Field(ge=64, le=16384)
    cpu_cores: float = Field(gt=0, le=8)
    disk_mb: int = Field(ge=64, le=16384)
    pids: int = Field(ge=8, le=4096)
    ttl_seconds: int = Field(ge=60, le=86400)
    command_timeout_seconds: int = Field(ge=1, le=3600)
    max_output_bytes: int = Field(ge=1024, le=10 * 1024 * 1024)


class SandboxSession(BaseModel):
    """A live or resumable workspace."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    vendor_id: str
    state: SandboxState
    image: str
    created_at: datetime
    expires_at: datetime
    workspace: str = "/workspace"
    command_timeout_seconds: int = Field(ge=1, le=3600)
    max_output_bytes: int = Field(ge=1024, le=10 * 1024 * 1024)


class ExecResult(BaseModel):
    """What a command did.

    `exit_code` is the answer; stdout and stderr are evidence. A caller that
    only reads stdout will eventually report success for a command that failed.
    """

    model_config = ConfigDict(extra="forbid")

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxCapabilities(BaseModel):
    """What a vendor actually does, stated rather than discovered."""

    model_config = ConfigDict(frozen=True)

    resumable: bool = False
    port_forwarding: bool = False
    host_allowlist: bool = False
    isolation: str = "container"


class SandboxError(Exception):
    """A sandbox operation failed."""

    def __init__(
        self, message: str, *, vendor: str | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.retryable = retryable


class SandboxUnavailable(SandboxError):
    """The sandbox runtime is not reachable.

    Separate because it means "this deployment has no Docker", which an
    operator fixes, rather than "this command failed", which an agent handles.
    """


def workspace_path(workspace: str, path: str) -> str:
    """Resolve a caller-supplied path inside the workspace, or refuse.

    Every read and write goes through this. Paths reach it from a model that
    has been reading untrusted documents, and `../../etc/shadow` is the whole
    attack — so containment is checked on the normalised path rather than by
    inspecting the string for suspicious sequences.
    """
    import posixpath

    root = posixpath.normpath(workspace)
    candidate = posixpath.normpath(posixpath.join(root, path.lstrip("/")))
    if candidate != root and not candidate.startswith(root + "/"):
        raise SandboxError(f"Path escapes the workspace: {path!r}")
    return candidate
