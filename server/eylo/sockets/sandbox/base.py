"""The sandbox vendor contract.

Six verbs, and each one is something a hosted vendor could also do — that is
the test for whether it belongs here rather than in the Docker adapter. There
is no general RPC into the sandbox, because a protocol that can express
anything cannot be reasoned about at a trust boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from eylo.sockets.sandbox.schemas import (
    ExecResult,
    SandboxCapabilities,
    SandboxManifest,
    SandboxSession,
)


class SandboxVendorAdapter(ABC):
    """Compute the agent can drive, isolated from everything else."""

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> SandboxCapabilities: ...

    @abstractmethod
    async def create(self, manifest: SandboxManifest) -> SandboxSession:
        """Start a session from a manifest.

        **Not an agent verb.** Session creation is an operator or platform
        decision — an agent that could create sandboxes could create them in a
        loop, and each one is memory, disk and money.
        """
        ...

    @abstractmethod
    async def exec(
        self, session: SandboxSession, command: str, *, timeout_seconds: int = 60
    ) -> ExecResult:
        """Run a command in the workspace and wait for it.

        A timeout is mandatory rather than optional. The thing being run was
        written by a model, and `while true` is a normal thing for a model to
        write by accident.
        """
        ...

    @abstractmethod
    async def read(self, session: SandboxSession, path: str) -> bytes:
        """Read a file from the workspace. Paths outside it must be refused."""
        ...

    @abstractmethod
    async def write(self, session: SandboxSession, path: str, content: bytes) -> None:
        """Write a file into the workspace. Paths outside it must be refused."""
        ...

    @abstractmethod
    async def export_workspace(
        self,
        session: SandboxSession,
        *,
        max_bytes: int,
    ) -> bytes:
        """Return one complete bounded archive; never return a partial archive."""
        ...

    @abstractmethod
    async def restore_workspace(
        self,
        session: SandboxSession,
        archive: bytes,
    ) -> None:
        """Restore a verified archive into a newly created empty workspace."""
        ...

    @abstractmethod
    async def list_vendor_ids(self) -> list[str]:
        """Every session this vendor is currently holding for us.

        The reaper reads the database, which is right for expiry but blind to
        the one case that matters most: a workspace whose row is gone. A row
        deleted by hand, lost to a restore, or never committed because the
        worker died between creating the container and recording it, leaves
        compute running that nothing will ever reclaim.

        Comparing this against what we have on record is how "nothing we made
        outlives us" becomes true rather than intended. A hosted vendor answers
        the same question by listing its own sessions.
        """
        ...

    @abstractmethod
    async def destroy_vendor_id(self, vendor_id: str) -> bool:
        """Tear down by the vendor's own handle, with no row to consult."""
        ...

    @abstractmethod
    async def destroy(self, session: SandboxSession) -> bool:
        """Tear the session down and delete its workspace.

        True when it is gone or was already gone — the state the caller asked
        for either way, so a retry after a partial failure is safe. Every
        session has an expiry and a reaper behind this, because a leaked
        container is a bill nobody notices.
        """
        ...
