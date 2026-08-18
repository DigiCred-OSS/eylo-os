"""Docker sandbox adapter with no network, a read-only root, and bounded tmpfs."""

from __future__ import annotations

import asyncio
import io
import posixpath
import socket
import tarfile
import time
import uuid
from collections.abc import Mapping
from datetime import timedelta

import arrow

from eylo.sockets.sandbox.base import SandboxVendorAdapter
from eylo.sockets.sandbox.schemas import (
    ExecResult,
    SandboxCapabilities,
    SandboxError,
    SandboxManifest,
    SandboxSession,
    SandboxState,
    SandboxUnavailable,
    workspace_path,
)

PROVIDER = "docker"
WORKSPACE = "/workspace"

# The unprivileged user commands run as. Fixed rather than taken from the image
# so a manifest naming an image whose default user is root does not get root.
RUN_UID = 65534
RUN_GID = 65534
RUN_AS = f"{RUN_UID}:{RUN_GID}"

# `/tmp` has to be writable for most tooling, and a read-only root makes it
# not. A capped tmpfs gives it back without giving back a writable root.
TMPFS_MB = 64

# Largest file this will move in or out. Reading a file into memory is how a
# sandbox takes down the worker driving it rather than itself.
MAX_FILE_BYTES = 32 * 1024 * 1024


def _remove_container(client, vendor_id: str) -> None:
    """Treat only Docker's explicit not-found response as successful cleanup."""
    from docker.errors import NotFound

    try:
        container = client.containers.get(vendor_id)
        container.remove(force=True)
    except NotFound:
        return
    except Exception as error:  # noqa: BLE001 - normalize Docker client failures
        raise SandboxError(
            "Could not destroy sandbox compute.",
            vendor=PROVIDER,
            retryable=True,
        ) from error


class DockerSandboxAdapter(SandboxVendorAdapter):
    """Ephemeral containers with bounded workspace export and restore."""

    def __init__(
        self,
        endpoint: str,
        client=None,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.startswith("unix:///"):
            raise SandboxError(
                "Docker requires an explicit absolute unix:// endpoint.",
                vendor=PROVIDER,
            )
        self._endpoint = endpoint
        self._client = client
        self._labels = dict(labels or {})

    def _docker(self):
        if self._client is None:
            import docker
            from docker.errors import DockerException

            try:
                self._client = docker.DockerClient(base_url=self._endpoint)
                self._client.ping()
            except DockerException as error:
                raise SandboxUnavailable(
                    "Docker is not reachable.", vendor=PROVIDER
                ) from error
        return self._client

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(
            resumable=True,
            port_forwarding=False,
            # Docker's own networking cannot express "these hosts and no
            # others" without a proxy. Reported as False rather than accepting
            # `allowed_hosts` and quietly ignoring it — a manifest that looks
            # enforced and is not is worse than one that is refused.
            host_allowlist=False,
            isolation="container",
        )

    # ---- lifecycle ---------------------------------------------------

    async def create(self, manifest: SandboxManifest) -> SandboxSession:
        if manifest.network or manifest.allowed_hosts:
            raise SandboxError(
                "Docker V1 cannot enforce destination-scoped egress; network "
                "and allowed_hosts must both remain disabled.",
                vendor=PROVIDER,
            )

        session_id = manifest.id
        client = self._docker()

        def start():
            return client.containers.run(
                manifest.image,
                # Idle forever; work arrives through `exec`. A container whose
                # entrypoint is the work would be a function call, not a
                # session.
                command=["sleep", str(manifest.ttl_seconds)],
                detach=True,
                name=f"eylo-sbx-{session_id}",
                labels={"eylo.sandbox": str(session_id), **self._labels},
                # Isolation is fixed by the adapter, not organization config.
                network_mode="none",
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                user=RUN_AS,
                privileged=False,
                mem_limit=f"{manifest.memory_mb}m",
                nano_cpus=int(manifest.cpu_cores * 1_000_000_000),
                pids_limit=manifest.pids,
                # Both writable areas are bounded tmpfs mounts. Docker named
                # volumes have no portable hard quota, so accepting a volume
                # ceiling would be a configuration lie.
                tmpfs={
                    WORKSPACE: (
                        f"size={manifest.disk_mb}m,mode=0700,"
                        f"uid={RUN_UID},gid={RUN_GID}"
                    ),
                    "/tmp": f"size={TMPFS_MB}m,mode=1777",
                },
                working_dir=WORKSPACE,
                environment=dict(manifest.env),
                auto_remove=False,
            )

        start_task = asyncio.create_task(asyncio.to_thread(start))
        try:
            container = await asyncio.shield(start_task)
        except asyncio.CancelledError:
            try:
                created = await start_task
            except Exception:  # noqa: BLE001 - cancellation remains authoritative
                pass
            else:
                await asyncio.to_thread(created.remove, force=True)
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not start a sandbox.", vendor=PROVIDER, retryable=True
            ) from error

        now = arrow.utcnow()
        session = SandboxSession(
            id=session_id,
            vendor_id=container.id,
            state=SandboxState.RUNNING,
            image=manifest.image,
            created_at=now.datetime,
            expires_at=now.shift(seconds=manifest.ttl_seconds).datetime,
            workspace=WORKSPACE,
            command_timeout_seconds=manifest.command_timeout_seconds,
            max_output_bytes=manifest.max_output_bytes,
        )

        try:
            for path, content in manifest.files.items():
                await self.write(session, path, content.encode("utf-8"))
        except Exception:
            await self.destroy(session)
            raise
        return session

    async def export_workspace(
        self,
        session: SandboxSession,
        *,
        max_bytes: int,
    ) -> bytes:
        """Export `/workspace` as one bounded archive or reject it whole."""
        if max_bytes < 1:
            raise SandboxError("Workspace archive ceiling must be positive.")
        client = self._docker()

        def export() -> bytes:
            container = client.containers.get(session.vendor_id)
            execution = client.api.exec_create(
                container.id,
                ["tar", "-cf", "-", "-C", session.workspace, "."],
                stdout=True,
                stderr=True,
                user=RUN_AS,
                workdir=session.workspace,
            )
            execution_id = execution["Id"]
            stream = client.api.exec_start(
                execution_id,
                stream=True,
                demux=True,
            )
            content = bytearray()
            errors = bytearray()
            for out_chunk, err_chunk in stream:
                content.extend(out_chunk or b"")
                errors.extend(err_chunk or b"")
                if len(content) > max_bytes:
                    if hasattr(stream, "close"):
                        stream.close()
                    container.kill()
                    raise SandboxError(
                        "Workspace archive exceeded its byte ceiling; no partial "
                        "checkpoint was returned.",
                        vendor=PROVIDER,
                    )
                if len(errors) > 64 * 1024:
                    if hasattr(stream, "close"):
                        stream.close()
                    container.kill()
                    raise SandboxError(
                        "Workspace export error output exceeded its safety limit.",
                        vendor=PROVIDER,
                    )
            inspected = client.api.exec_inspect(execution_id)
            if inspected.get("ExitCode") != 0:
                raise SandboxError(
                    "Could not export the sandbox workspace.",
                    vendor=PROVIDER,
                )
            archive = bytes(content)
            _validate_workspace_archive(archive)
            return archive

        try:
            return await asyncio.to_thread(export)
        except SandboxError:
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not export the sandbox workspace.",
                vendor=PROVIDER,
                retryable=True,
            ) from error

    async def restore_workspace(
        self,
        session: SandboxSession,
        archive: bytes,
    ) -> None:
        """Restore one validated checkpoint into a fresh tmpfs workspace."""
        _validate_workspace_archive(archive)
        client = self._docker()

        def restore() -> None:
            container = client.containers.get(session.vendor_id)
            execution = client.api.exec_create(
                container.id,
                [
                    "tar",
                    "-xf",
                    "-",
                    "-C",
                    session.workspace,
                    "--no-same-permissions",
                ],
                stdin=True,
                stdout=True,
                stderr=True,
                user=RUN_AS,
                workdir=session.workspace,
            )
            execution_id = execution["Id"]
            channel = client.api.exec_start(execution_id, socket=True)
            _send_stdin(channel, archive)
            _consume_exec_output(channel)
            inspected = _wait_for_exec(client, execution_id)
            if inspected.get("ExitCode") != 0:
                raise SandboxError(
                    "Docker refused the complete workspace checkpoint.",
                    vendor=PROVIDER,
                )

        try:
            await asyncio.to_thread(restore)
        except SandboxError:
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not restore the sandbox workspace.",
                vendor=PROVIDER,
                retryable=True,
            ) from error

    async def destroy(self, session: SandboxSession) -> bool:
        """Remove the container. Idempotent."""
        client = self._docker()
        await asyncio.to_thread(_remove_container, client, session.vendor_id)
        return True

    async def list_vendor_ids(self) -> list[str]:
        """Container ids carrying our label, whatever the platform remembers."""
        client = self._docker()

        def listing():
            return [
                container.id
                for container in client.containers.list(
                    all=True,
                    filters={
                        "label": [
                            "eylo.sandbox",
                            *(f"{key}={value}" for key, value in self._labels.items()),
                        ]
                    },
                )
            ]

        return await asyncio.to_thread(listing)

    async def destroy_vendor_id(self, vendor_id: str) -> bool:
        """Remove a labeled container knowing only the provider handle."""
        client = self._docker()
        await asyncio.to_thread(_remove_container, client, vendor_id)
        return True

    # ---- work --------------------------------------------------------

    async def exec(
        self, session: SandboxSession, command: str, *, timeout_seconds: int = 60
    ) -> ExecResult:
        """Run a command, bounded by a wall clock.

        The timeout is enforced by this side rather than trusted to the
        container: `docker exec` has no timeout of its own, so a command that
        never returns would hold the calling worker forever.
        """
        client = self._docker()
        started = arrow.utcnow()

        container = client.containers.get(session.vendor_id)
        effective_timeout = min(timeout_seconds, session.command_timeout_seconds)

        def run():
            execution = client.api.exec_create(
                container.id,
                ["/bin/sh", "-c", command],
                user=RUN_AS,
                workdir=session.workspace,
            )
            execution_id = execution["Id"]
            output = client.api.exec_start(
                execution_id,
                stream=True,
                demux=True,
            )
            stdout = bytearray()
            stderr = bytearray()
            for out_chunk, err_chunk in output:
                stdout.extend(out_chunk or b"")
                stderr.extend(err_chunk or b"")
                if len(stdout) + len(stderr) > session.max_output_bytes:
                    raise _OutputLimitExceeded
            inspected = client.api.exec_inspect(execution_id)
            return inspected.get("ExitCode"), bytes(stdout), bytes(stderr)

        task = asyncio.create_task(asyncio.to_thread(run))
        try:
            exit_code, stdout, stderr = await asyncio.wait_for(
                asyncio.shield(task), timeout=effective_timeout
            )
        except asyncio.CancelledError:
            await asyncio.to_thread(container.kill)
            await _confirm_worker_stopped(task, container, client)
            raise
        except TimeoutError:
            await asyncio.to_thread(container.kill)
            await _confirm_worker_stopped(task, container, client)
            return ExecResult(
                exit_code=124,
                stdout="",
                stderr=(
                    f"Command exceeded {effective_timeout}s; the sandbox was "
                    "terminated before returning."
                ),
                timed_out=True,
                duration_seconds=(arrow.utcnow() - started).total_seconds(),
            )
        except _OutputLimitExceeded:
            await asyncio.to_thread(container.kill)
            await _confirm_worker_stopped(task, container, client)
            raise SandboxError(
                "Command output exceeded the configured byte ceiling; the "
                "sandbox was terminated and no partial output was returned.",
                vendor=PROVIDER,
            ) from None
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not run a command.", vendor=PROVIDER, retryable=True
            ) from error

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")

        # A sandbox that has exhausted its own process limit cannot start the
        # next command either, and Docker reports that as an OCI error nobody
        # reading it would connect to the fork bomb three commands ago. The
        # limit did its job — the host is fine — but the session is spent, and
        # saying so is the difference between an actionable message and a
        # confusing one.
        #
        # Matched on Docker's message because there is no other signal: the
        # exec never started, so there is no exit status of its own. If the
        # wording changes, the fallback is the raw error, which is what a
        # caller got before this existed.
        if exit_code in (126, 127, 128) and _cannot_start(out + err):
            return ExecResult(
                exit_code=exit_code or 128,
                stdout=out,
                stderr=(
                    "This sandbox has run out of processes and can no longer "
                    "start commands. Its limits held — the host is unaffected "
                    "— but the session is spent and should be recreated. "
                    f"Docker said: {(err or out).strip()[:200]}"
                ),
                duration_seconds=(arrow.utcnow() - started).total_seconds(),
            )

        return ExecResult(
            exit_code=exit_code if exit_code is not None else -1,
            stdout=out,
            stderr=err,
            duration_seconds=(arrow.utcnow() - started).total_seconds(),
        )

    async def resolve_image(self, image: str) -> tuple[str, str]:
        """Resolve/pull the configured image and return immutable runtime evidence."""
        client = self._docker()

        def resolve() -> tuple[str, str]:
            try:
                selected = client.images.get(image)
            except Exception:
                selected = client.images.pull(image)
            selected.reload()
            version = str(client.version().get("Version") or "").strip()
            image_id = str(selected.id or "").strip()
            if not version or not image_id:
                raise SandboxError(
                    "Docker did not return image or server-version evidence.",
                    vendor=PROVIDER,
                )
            return image_id, version

        try:
            return await asyncio.to_thread(resolve)
        except SandboxError:
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxUnavailable(
                "Docker image verification failed.",
                vendor=PROVIDER,
            ) from error

    async def verify_runtime(self, manifest: SandboxManifest) -> None:
        """Exercise the exact isolation, exec, and file path with zero residue."""
        session = None
        restored_session = None
        try:
            session = await self.create(manifest)
            container = self._docker().containers.get(session.vendor_id)
            await asyncio.to_thread(container.reload)
            host_config = container.attrs.get("HostConfig", {})
            tmpfs = host_config.get("Tmpfs") or {}
            if (
                host_config.get("NetworkMode") != "none"
                or host_config.get("ReadonlyRootfs") is not True
                or host_config.get("Privileged") is not False
                or "ALL" not in (host_config.get("CapDrop") or [])
                or WORKSPACE not in tmpfs
            ):
                raise SandboxError(
                    "Docker did not apply the verified isolation policy.",
                    vendor=PROVIDER,
                )
            result = await self.exec(
                session,
                "printf eylo-sandbox-ok",
                timeout_seconds=manifest.command_timeout_seconds,
            )
            if not result.ok or result.stdout != "eylo-sandbox-ok" or result.stderr:
                raise SandboxError(
                    "Docker verification command failed.",
                    vendor=PROVIDER,
                )
            sentinel = b"sandbox-file-ok"
            await self.write(session, ".eylo-verification", sentinel)
            if await self.read(session, ".eylo-verification") != sentinel:
                raise SandboxError(
                    "Docker verification file round trip failed.",
                    vendor=PROVIDER,
                )
            checkpoint = await self.export_workspace(
                session,
                max_bytes=manifest.disk_mb * 2 * 1024 * 1024,
            )
            await self.destroy(session)
            session = None
            restored_session = await self.create(
                manifest.model_copy(update={"id": uuid.uuid4()})
            )
            await self.restore_workspace(restored_session, checkpoint)
            if await self.read(restored_session, ".eylo-verification") != sentinel:
                raise SandboxError(
                    "Docker verification checkpoint restore failed.",
                    vendor=PROVIDER,
                )
        finally:
            if session is not None:
                await self.destroy(session)
                if session.vendor_id in await self.list_vendor_ids():
                    raise SandboxError(
                        "Docker verification left a live sandbox resource.",
                        vendor=PROVIDER,
                    )
            if restored_session is not None:
                await self.destroy(restored_session)
                if restored_session.vendor_id in await self.list_vendor_ids():
                    raise SandboxError(
                        "Docker verification left a restored sandbox resource.",
                        vendor=PROVIDER,
                    )

    async def verify_limits(self, manifest: SandboxManifest) -> None:
        """Prove timeout/output ceilings terminate compute and return no partials."""
        timeout_session = None
        output_session = None
        try:
            timeout_session = await self.create(
                manifest.model_copy(update={"id": uuid.uuid4()})
            )
            timed_out = await self.exec(
                timeout_session,
                f"sleep {manifest.command_timeout_seconds + 5}",
                timeout_seconds=manifest.command_timeout_seconds,
            )
            timeout_container = self._docker().containers.get(timeout_session.vendor_id)
            await asyncio.to_thread(timeout_container.reload)
            timeout_status = timeout_container.attrs.get("State", {}).get("Status")
            if (
                not timed_out.timed_out
                or timed_out.stdout
                or timeout_status not in {"exited", "dead"}
            ):
                raise SandboxError(
                    "Docker did not contain the verification timeout.",
                    vendor=PROVIDER,
                )
            await self.destroy(timeout_session)
            timeout_session = None

            output_session = await self.create(
                manifest.model_copy(update={"id": uuid.uuid4()})
            )
            try:
                await self.exec(output_session, "yes eylo-output-limit")
            except SandboxError as error:
                if "no partial output" not in str(error):
                    raise
            else:
                raise SandboxError(
                    "Docker returned output beyond the configured ceiling.",
                    vendor=PROVIDER,
                )
        finally:
            if timeout_session is not None:
                await self.destroy(timeout_session)
            if output_session is not None:
                await self.destroy(output_session)

    async def read(self, session: SandboxSession, path: str) -> bytes:
        target = workspace_path(session.workspace, path)
        client = self._docker()

        def fetch():
            container = client.containers.get(session.vendor_id)
            execution = client.api.exec_create(
                container.id,
                ["/bin/sh", "-c", 'cat "$1"', "eylo-read", target],
                stdout=True,
                stderr=True,
                user=RUN_AS,
                workdir=session.workspace,
            )
            execution_id = execution["Id"]
            output = client.api.exec_start(
                execution_id,
                stream=True,
                demux=True,
            )
            content = bytearray()
            errors = bytearray()
            for out_chunk, err_chunk in output:
                content.extend(out_chunk or b"")
                errors.extend(err_chunk or b"")
                if len(content) + len(errors) > MAX_FILE_BYTES:
                    if hasattr(output, "close"):
                        output.close()
                    raise SandboxError(
                        f"{path} exceeds the {MAX_FILE_BYTES} byte limit.",
                        vendor=PROVIDER,
                    )
            inspected = client.api.exec_inspect(execution_id)
            if inspected.get("ExitCode") != 0:
                raise SandboxError(
                    "Could not read the sandbox file.",
                    vendor=PROVIDER,
                )
            return bytes(content)

        try:
            return await asyncio.to_thread(fetch)
        except SandboxError:
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not read the sandbox file.", vendor=PROVIDER
            ) from error

    async def write(self, session: SandboxSession, path: str, content: bytes) -> None:
        target = workspace_path(session.workspace, path)
        if len(content) > MAX_FILE_BYTES:
            raise SandboxError(
                f"{path} is {len(content)} bytes, over the {MAX_FILE_BYTES} "
                "byte limit.",
                vendor=PROVIDER,
            )
        client = self._docker()
        directory, _ = posixpath.split(target)

        def put():
            container = client.containers.get(session.vendor_id)
            execution = client.api.exec_create(
                container.id,
                [
                    "/bin/sh",
                    "-c",
                    'mkdir -p "$1" && umask 022 && cat > "$2"',
                    "eylo-write",
                    directory,
                    target,
                ],
                stdin=True,
                stdout=True,
                stderr=True,
                user=RUN_AS,
                workdir=session.workspace,
            )
            execution_id = execution["Id"]
            channel = client.api.exec_start(execution_id, socket=True)
            _send_stdin(channel, content)
            _consume_exec_output(channel)
            inspected = _wait_for_exec(client, execution_id)
            if inspected.get("ExitCode") != 0:
                raise SandboxError(
                    "Could not write the sandbox file.",
                    vendor=PROVIDER,
                )

        try:
            await asyncio.to_thread(put)
        except SandboxError:
            raise
        except Exception as error:  # noqa: BLE001 - docker raises many types
            raise SandboxError(
                "Could not write the sandbox file.", vendor=PROVIDER
            ) from error


def _cannot_start(output: str) -> bool:
    """Whether Docker failed to start the exec rather than running it."""
    lowered = output.lower()
    return "oci runtime exec failed" in lowered or (
        "unable to start container process" in lowered
    )


def _validate_workspace_archive(content: bytes) -> None:
    """Reject malformed, escaping, or special-file checkpoints before restore."""
    if not content:
        raise SandboxError("Workspace checkpoint is empty.", vendor=PROVIDER)
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            members = archive.getmembers()
            if not members:
                raise SandboxError(
                    "Workspace checkpoint contains no archive members.",
                    vendor=PROVIDER,
                )
            for member in members:
                path = posixpath.normpath(member.name)
                if path.startswith("/") or path == ".." or path.startswith("../"):
                    raise SandboxError(
                        "Workspace checkpoint contains an escaping path.",
                        vendor=PROVIDER,
                    )
                if not (member.isdir() or member.isfile()):
                    raise SandboxError(
                        "Workspace checkpoint contains an unsupported special file.",
                        vendor=PROVIDER,
                    )
    except SandboxError:
        raise
    except (tarfile.TarError, OSError) as error:
        raise SandboxError(
            "Workspace checkpoint is not a valid archive.",
            vendor=PROVIDER,
        ) from error


class _OutputLimitExceeded(Exception):
    pass


async def _confirm_worker_stopped(task, container, client) -> None:
    """Do not return while a timed-out Docker exec can still mutate the workspace."""
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=10)
    except _OutputLimitExceeded:
        return
    except TimeoutError:
        await asyncio.to_thread(container.remove, force=True)
    except Exception:  # noqa: BLE001 - killed exec reports vendor-specific errors
        return
    else:
        return

    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=10)
    except TimeoutError:
        await asyncio.to_thread(client.close)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        except Exception as error:  # noqa: BLE001 - containment failure is terminal
            raise SandboxError(
                "Docker did not confirm command termination.",
                vendor=PROVIDER,
            ) from error
    except _OutputLimitExceeded:
        return
    except Exception:  # noqa: BLE001 - killed exec reports vendor-specific errors
        return


def _send_stdin(channel, content: bytes) -> None:
    raw_socket = getattr(channel, "_sock", channel)
    if hasattr(raw_socket, "sendall"):
        raw_socket.sendall(content)
    else:
        channel.write(content)
        if hasattr(channel, "flush"):
            channel.flush()
    raw_socket.shutdown(socket.SHUT_WR)


def _consume_exec_output(channel) -> str:
    from docker.utils.socket import STDERR, frames_iter

    if not hasattr(channel, "fileno"):
        while channel.recv(4096):
            pass
        return ""
    errors = bytearray()
    for stream, data in frames_iter(channel, tty=False):
        if stream == STDERR:
            errors.extend(data)
            if len(errors) > 64 * 1024:
                raise SandboxError(
                    "Sandbox file-write error output exceeded its safety limit.",
                    vendor=PROVIDER,
                )
    return errors.decode("utf-8", errors="replace")


def _wait_for_exec(client, execution_id: str) -> dict:
    deadline = time.monotonic() + 10
    while True:
        inspected = client.api.exec_inspect(execution_id)
        if not inspected.get("Running", False):
            return inspected
        if time.monotonic() >= deadline:
            raise SandboxError(
                "Sandbox file write did not finish within 10 seconds.",
                vendor=PROVIDER,
            )
        time.sleep(0.01)


def expiry_horizon(seconds: int):
    """When a session created now would expire. Used by the reaper."""
    return arrow.utcnow().shift(seconds=seconds).datetime - timedelta(0)
