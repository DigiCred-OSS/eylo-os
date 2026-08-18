"""Orchestrate explicitly authorized sandbox sessions and durable workspaces."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from uuid import UUID

import arrow
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.sandbox import (
    SandboxAccess,
    SandboxError,
    SandboxSession,
    SandboxState,
)
from eylo.common.database import async_session_factory
from eylo.modules.sandbox.access import SandboxAccessError, assert_can_run
from eylo.modules.sandbox.models import (
    SandboxGrantModel,
    SandboxSessionModel,
    SandboxWorkspaceCheckpointModel,
)
from eylo.pipelines.sandbox.resolver import (
    resolve_pinned_sandbox_adapter,
    resolve_sandbox_adapter,
)

logger = logging.getLogger(__name__)

_LIVE_STATES = (SandboxState.STARTING, SandboxState.RUNNING, SandboxState.PAUSED)
_TOOL_RESULT_LIMIT_BYTES = 16_384


class SandboxQuotaExceeded(SandboxError):
    """A hard organization or agent session ceiling was reached."""


@dataclass(frozen=True, slots=True)
class WorkspaceExport:
    """Complete secret-free checkpoint material exported from one session."""

    session_id: UUID
    agent_run_id: UUID
    provider: str
    image: str
    sandbox_provider_config_id: UUID
    sandbox_provider_config_revision: int
    grant_id: UUID | None
    grant_revision: int | None
    effective_policy: dict
    workspace_digest: str
    archive: bytes


def _to_session(row: SandboxSessionModel) -> SandboxSession:
    if row.vendor_id is None:
        raise SandboxError(f"Sandbox session {row.id} is not running.")
    policy = row.effective_policy
    return SandboxSession(
        id=row.id,
        vendor_id=row.vendor_id,
        state=row.state,
        image=row.image,
        created_at=row.created_at,
        expires_at=row.expires_at,
        workspace=row.workspace,
        command_timeout_seconds=int(policy["command_timeout_seconds"]),
        max_output_bytes=int(policy["max_output_bytes"]),
    )


async def grants_for_agent(
    agent_id: UUID,
    *,
    organization_id: UUID | None = None,
) -> list[SandboxGrantModel]:
    """Return the active grant, optionally constrained by its owning org."""
    async with async_session_factory() as db:
        query = select(SandboxGrantModel).where(
            SandboxGrantModel.agent_id == agent_id,
            SandboxGrantModel.deleted.is_(False),
        )
        if organization_id is not None:
            query = query.where(SandboxGrantModel.organization_id == organization_id)
        return list((await db.execute(query)).scalars().all())


async def grant(
    *,
    organization_id: UUID,
    agent_id: UUID,
    sandbox_provider_config_id: UUID,
    access: SandboxAccess,
    max_sessions: int | None = None,
) -> SandboxGrantModel:
    """Bind one agent to one ready sandbox config and no-egress permission."""
    from eylo.modules.agents.models import AgentsModel

    if access is not SandboxAccess.RUN:
        raise SandboxError(
            "Docker V1 supports RUN only. Destination-scoped network egress is "
            "not available."
        )
    if max_sessions is not None and (
        isinstance(max_sessions, bool)
        or not isinstance(max_sessions, int)
        or not 1 <= max_sessions <= 100
    ):
        raise SandboxError("max_sessions must be an integer between 1 and 100.")
    async with async_session_factory() as db:
        await _lock_agent_grant(db, agent_id)
        agent = await db.scalar(
            select(AgentsModel.id).where(
                AgentsModel.id == agent_id,
                AgentsModel.organization_id == organization_id,
                AgentsModel.deleted.is_(False),
            )
        )
        if agent is None:
            raise SandboxError(f"No agent {agent_id} in this organization.")
        _, resolved = await resolve_sandbox_adapter(
            organization_id,
            provider_config_id=sandbox_provider_config_id,
            db=db,
        )
        if max_sessions is not None and max_sessions > resolved.max_sessions:
            raise SandboxError(
                f"max_sessions cannot exceed the selected sandbox config limit "
                f"of {resolved.max_sessions}."
            )
        existing = await db.scalar(
            select(SandboxGrantModel).where(
                SandboxGrantModel.organization_id == organization_id,
                SandboxGrantModel.agent_id == agent_id,
            )
        )
        if existing is not None:
            existing.deleted = False
            existing.access = access
            existing.max_sessions = max_sessions
            existing.sandbox_provider_config_id = resolved.provider_config_id
            existing.sandbox_provider_config_revision = (
                resolved.provider_config_revision
            )
            existing.revision += 1
            await db.commit()
            await db.refresh(existing)
            return existing

        row = SandboxGrantModel(
            organization_id=organization_id,
            agent_id=agent_id,
            sandbox_provider_config_id=resolved.provider_config_id,
            sandbox_provider_config_revision=resolved.provider_config_revision,
            access=access,
            max_sessions=max_sessions,
            revision=1,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row


async def revoke(*, organization_id: UUID, agent_id: UUID) -> bool:
    """Block later acquisitions without interrupting an authorized action."""
    async with async_session_factory() as db:
        await _lock_agent_grant(db, agent_id)
        row = await db.scalar(
            select(SandboxGrantModel).where(
                SandboxGrantModel.organization_id == organization_id,
                SandboxGrantModel.agent_id == agent_id,
                SandboxGrantModel.deleted.is_(False),
            )
        )
        if row is None:
            return False
        row.deleted = True
        row.revision += 1
        await db.commit()
        return True


async def list_grants(*, organization_id: UUID) -> list[SandboxGrantModel]:
    """List active sandbox grants owned by one organization."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(SandboxGrantModel)
            .where(
                SandboxGrantModel.organization_id == organization_id,
                SandboxGrantModel.deleted.is_(False),
            )
            .order_by(SandboxGrantModel.created_at.desc())
        )
        return list(result.scalars().all())


async def acquire(
    *,
    organization_id: UUID,
    sandbox_provider_config_id: UUID | None = None,
    agent_id: UUID | None = None,
    agent_run_id: UUID | None = None,
    files: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
):
    """Authorize current access, then atomically reserve one pinned workspace."""
    checkpoint_archive: bytes | None = None
    checkpoint_digest: str | None = None
    async with async_session_factory() as db:
        await _lock_capacity(db, organization_id, agent_id, agent_run_id)
        if agent_run_id is not None and agent_id is None:
            raise SandboxAccessError(
                "AgentRun sandbox acquisition requires an identified agent."
            )
        grant_row = (
            await _require_active_grant(db, organization_id, agent_id)
            if agent_id is not None
            else None
        )
        existing = await _existing_run_session(db, organization_id, agent_run_id)
        if existing is not None:
            assert grant_row is not None
            if not _same_identifier(existing.agent_id, agent_id):
                raise SandboxAccessError(
                    "The current sandbox grant does not authorize this workspace."
                )
            _assert_grant_authorizes(
                grant_row,
                agent_id=agent_id,
                grant_id=existing.grant_id,
                provider_config_id=existing.sandbox_provider_config_id,
                provider_config_revision=existing.sandbox_provider_config_revision,
            )
            adapter, resolved = await resolve_pinned_sandbox_adapter(
                organization_id,
                provider_config_id=existing.sandbox_provider_config_id,
                provider_config_revision=existing.sandbox_provider_config_revision,
                db=db,
            )
            existing.grant_id = grant_row.id
            existing.grant_revision = grant_row.revision
            existing.effective_policy = _effective_policy(
                resolved,
                grant_max_sessions=grant_row.max_sessions,
            )
            await db.commit()
            return adapter, _to_session(existing)

        checkpoint = await _latest_checkpoint(db, organization_id, agent_run_id)
        if checkpoint is not None and files:
            raise SandboxError(
                "Restored workspaces cannot replace their staged inputs."
            )
        if checkpoint is not None:
            assert grant_row is not None
            _assert_grant_authorizes(
                grant_row,
                agent_id=agent_id,
                grant_id=checkpoint.grant_id,
                provider_config_id=checkpoint.sandbox_provider_config_id,
                provider_config_revision=checkpoint.sandbox_provider_config_revision,
            )
            adapter, resolved = await resolve_pinned_sandbox_adapter(
                organization_id,
                provider_config_id=checkpoint.sandbox_provider_config_id,
                provider_config_revision=checkpoint.sandbox_provider_config_revision,
                db=db,
            )
            _assert_checkpoint_matches_resolved(checkpoint, resolved)
            effective_policy = _effective_policy(
                resolved,
                grant_max_sessions=grant_row.max_sessions,
            )
            checkpoint_archive = bytes(checkpoint.workspace_archive)
            checkpoint_digest = checkpoint.workspace_digest
        if checkpoint is None and agent_id is not None:
            assert grant_row is not None
            selected_config_id = grant_row.sandbox_provider_config_id
            if sandbox_provider_config_id is not None and not _same_identifier(
                sandbox_provider_config_id,
                selected_config_id,
            ):
                raise SandboxAccessError(
                    "Requested sandbox config does not match the agent's grant."
                )
        elif checkpoint is None and sandbox_provider_config_id is None:
            raise SandboxError(
                "A direct sandbox invocation requires sandbox_provider_config_id."
            )
        elif checkpoint is None:
            selected_config_id = sandbox_provider_config_id

        if checkpoint is None:
            adapter, resolved = await resolve_sandbox_adapter(
                organization_id,
                provider_config_id=selected_config_id,
                db=db,
            )
            effective_policy = _effective_policy(
                resolved,
                grant_max_sessions=(
                    grant_row.max_sessions if grant_row is not None else None
                ),
            )
        await _assert_capacity(
            db,
            organization_id,
            agent_id,
            effective_policy,
        )
        now = arrow.utcnow()
        reservation = SandboxSessionModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            vendor_id=None,
            provider=adapter.provider,
            image=resolved.verified_image_id,
            sandbox_provider_config_id=resolved.provider_config_id,
            sandbox_provider_config_revision=resolved.provider_config_revision,
            grant_id=grant_row.id if grant_row is not None else None,
            grant_revision=grant_row.revision if grant_row is not None else None,
            effective_policy=effective_policy,
            state=SandboxState.STARTING,
            workspace="/workspace",
            expires_at=now.shift(seconds=int(resolved.config["ttl_seconds"])).datetime,
            last_used_at=now.datetime,
        )
        db.add(reservation)
        await db.commit()

    manifest = resolved.manifest(
        session_id=reservation.id,
        files=files or {},
        env=env or {},
    )
    session: SandboxSession | None = None
    try:
        session = await adapter.create(manifest)
        if checkpoint_archive is not None:
            if hashlib.sha256(checkpoint_archive).hexdigest() != checkpoint_digest:
                raise SandboxError("Sandbox workspace checkpoint digest mismatch.")
            await adapter.restore_workspace(session, checkpoint_archive)
    except Exception:
        await _cleanup_failed_acquisition(
            adapter=adapter,
            session=session,
            reservation_id=reservation.id,
        )
        raise

    try:
        await _activate_reservation(organization_id, reservation.id, session)
    except Exception:
        await _cleanup_failed_acquisition(
            adapter=adapter,
            session=session,
            reservation_id=reservation.id,
        )
        raise
    return adapter, session


async def _cleanup_failed_acquisition(
    *,
    adapter,
    session: SandboxSession | None,
    reservation_id: UUID,
) -> None:
    """Attempt both cleanup legs without hiding the acquisition failure."""
    if session is not None:
        try:
            await adapter.destroy(session)
        except Exception as error:  # noqa: BLE001 - reservation cleanup must still run
            logger.error(
                "Failed to destroy sandbox=%s after acquisition error_type=%s",
                session.id,
                type(error).__name__,
            )
    try:
        await _retire_reservation(reservation_id)
    except Exception as error:  # noqa: BLE001 - preserve original acquisition failure
        logger.error(
            "Failed to retire sandbox reservation=%s error_type=%s",
            reservation_id,
            type(error).__name__,
        )


async def discard_live_run_sessions(
    *,
    organization_id: UUID,
    agent_run_id: UUID,
) -> None:
    """Destroy any uncommitted workspace before a retried sandbox step."""
    async with async_session_factory() as db:
        rows = list(
            (
                await db.execute(
                    select(SandboxSessionModel).where(
                        SandboxSessionModel.organization_id == organization_id,
                        SandboxSessionModel.agent_run_id == agent_run_id,
                        SandboxSessionModel.state.in_(_LIVE_STATES),
                        SandboxSessionModel.deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
    for row in rows:
        if row.vendor_id is None:
            await _mark_destroyed(row.id)
            continue
        adapter, _ = await _resolve_pinned_adapter(
            organization_id,
            provider_config_id=row.sandbox_provider_config_id,
            provider_config_revision=row.sandbox_provider_config_revision,
        )
        await _destroy_and_mark(adapter, _to_session(row))


async def export_and_destroy_workspace(session: SandboxSession) -> WorkspaceExport:
    """Export one whole workspace, verify it, then release all compute."""
    row = await _session_row(session.id)
    if row.agent_run_id is None:
        raise SandboxError("Only AgentRun sandboxes can create durable checkpoints.")
    adapter, _ = await _resolve_pinned_adapter(
        row.organization_id,
        provider_config_id=row.sandbox_provider_config_id,
        provider_config_revision=row.sandbox_provider_config_revision,
    )
    disk_bytes = int(row.effective_policy["disk_mb"]) * 1024 * 1024
    try:
        archive = await adapter.export_workspace(session, max_bytes=disk_bytes * 2)
        return WorkspaceExport(
            session_id=row.id,
            agent_run_id=row.agent_run_id,
            provider=row.provider,
            image=row.image,
            sandbox_provider_config_id=row.sandbox_provider_config_id,
            sandbox_provider_config_revision=row.sandbox_provider_config_revision,
            grant_id=row.grant_id,
            grant_revision=row.grant_revision,
            effective_policy=dict(row.effective_policy),
            workspace_digest=hashlib.sha256(archive).hexdigest(),
            archive=archive,
        )
    finally:
        await _destroy_and_mark(adapter, session)


async def _destroy_and_mark(adapter, session: SandboxSession) -> None:
    """Finish provider cleanup even when the caller is being cancelled."""

    async def clean() -> None:
        await adapter.destroy(session)
        await _mark_destroyed(session.id)

    cleanup = asyncio.create_task(clean())
    try:
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        await cleanup
        raise


async def store_workspace_checkpoint_in_transaction(
    db: AsyncSession,
    *,
    organization_id: UUID,
    source_step_key: str,
    exported: WorkspaceExport,
    tool_result: dict | None = None,
) -> SandboxWorkspaceCheckpointModel:
    """Append one immutable checkpoint in the sandbox-step output transaction."""
    if exported.agent_run_id is None:
        raise SandboxError("Workspace export has no AgentRun authority.")
    _validate_tool_result(tool_result)
    await db.execute(
        select(
            func.pg_advisory_xact_lock(_lock_key("checkpoint", exported.agent_run_id))
        )
    )
    existing = await db.scalar(
        select(SandboxWorkspaceCheckpointModel).where(
            SandboxWorkspaceCheckpointModel.organization_id == organization_id,
            SandboxWorkspaceCheckpointModel.agent_run_id == exported.agent_run_id,
            SandboxWorkspaceCheckpointModel.source_step_key == source_step_key,
        )
    )
    if existing is not None:
        if (
            existing.workspace_digest != exported.workspace_digest
            or bytes(existing.workspace_archive) != exported.archive
            or existing.tool_result != tool_result
        ):
            raise SandboxError("Sandbox step already has a different checkpoint.")
        return existing
    revision = (
        await db.scalar(
            select(
                func.coalesce(func.max(SandboxWorkspaceCheckpointModel.revision), 0)
            ).where(
                SandboxWorkspaceCheckpointModel.organization_id == organization_id,
                SandboxWorkspaceCheckpointModel.agent_run_id == exported.agent_run_id,
            )
        )
        or 0
    ) + 1
    checkpoint = SandboxWorkspaceCheckpointModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        agent_run_id=exported.agent_run_id,
        revision=revision,
        source_step_key=source_step_key,
        provider=exported.provider,
        image=exported.image,
        sandbox_provider_config_id=exported.sandbox_provider_config_id,
        sandbox_provider_config_revision=exported.sandbox_provider_config_revision,
        grant_id=exported.grant_id,
        grant_revision=exported.grant_revision,
        effective_policy=exported.effective_policy,
        workspace_digest=exported.workspace_digest,
        byte_size=len(exported.archive),
        workspace_archive=exported.archive,
        tool_result=tool_result,
    )
    db.add(checkpoint)
    await db.flush()
    return checkpoint


async def workspace_checkpoint_for_step(
    *,
    organization_id: UUID,
    agent_run_id: UUID,
    source_step_key: str,
) -> SandboxWorkspaceCheckpointModel | None:
    """Load one private checkpoint by its durable product-step identity."""
    async with async_session_factory() as db:
        return await db.scalar(
            select(SandboxWorkspaceCheckpointModel).where(
                SandboxWorkspaceCheckpointModel.organization_id == organization_id,
                SandboxWorkspaceCheckpointModel.agent_run_id == agent_run_id,
                SandboxWorkspaceCheckpointModel.source_step_key == source_step_key,
                SandboxWorkspaceCheckpointModel.deleted.is_(False),
            )
        )


def _validate_tool_result(tool_result: dict | None) -> None:
    if tool_result is None:
        return
    if not isinstance(tool_result, dict):
        raise SandboxError("Sandbox tool result must be an object.")
    try:
        encoded = json.dumps(
            tool_result,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SandboxError("Sandbox tool result is not JSON-safe.") from error
    if len(encoded) > _TOOL_RESULT_LIMIT_BYTES:
        raise SandboxError(
            "Sandbox tool result exceeds its private checkpoint byte ceiling."
        )


async def release(session: SandboxSession, *, keep: bool = True) -> None:
    """Release compute; Docker V1 destroys because it cannot snapshot safely."""
    row = await _session_row(session.id)
    adapter, _ = await _resolve_pinned_adapter(
        row.organization_id,
        provider_config_id=row.sandbox_provider_config_id,
        provider_config_revision=row.sandbox_provider_config_revision,
    )
    if keep:
        logger.info(
            "Sandbox %s requested continuity, but Docker V1 is non-resumable; "
            "destroying compute until durable snapshot/restore is available.",
            session.id,
        )
    await adapter.destroy(session)
    await _mark_destroyed(session.id)


async def reap_expired() -> dict[str, int]:
    """Destroy expired pinned sessions, including abandoned reservations."""
    now = arrow.utcnow().datetime
    async with async_session_factory() as db:
        rows = list(
            (
                await db.execute(
                    select(SandboxSessionModel).where(
                        SandboxSessionModel.expires_at < now,
                        SandboxSessionModel.state != SandboxState.DESTROYED,
                        SandboxSessionModel.deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )

    destroyed = failed = 0
    for row in rows:
        try:
            if row.vendor_id is not None:
                adapter, _ = await _resolve_pinned_adapter(
                    row.organization_id,
                    provider_config_id=row.sandbox_provider_config_id,
                    provider_config_revision=row.sandbox_provider_config_revision,
                )
                await adapter.destroy(_to_session(row))
            await _mark_destroyed(row.id)
            destroyed += 1
        except Exception as error:  # noqa: BLE001 - one leak must not stop cleanup
            logger.error(
                "Could not destroy expired sandbox=%s error_type=%s",
                row.id,
                type(error).__name__,
            )
            failed += 1
    return {"destroyed": destroyed, "failed": failed}


async def list_sessions(
    *,
    organization_id: UUID,
    include_destroyed: bool = False,
    limit: int = 50,
) -> list[SandboxSessionModel]:
    async with async_session_factory() as db:
        query = select(SandboxSessionModel).where(
            SandboxSessionModel.organization_id == organization_id
        )
        if not include_destroyed:
            query = query.where(SandboxSessionModel.state != SandboxState.DESTROYED)
        query = query.order_by(SandboxSessionModel.created_at.desc()).limit(limit)
        return list((await db.execute(query)).scalars().all())


async def get_session(
    session_id: UUID,
    organization_id: UUID,
) -> SandboxSessionModel:
    async with async_session_factory() as db:
        row = await db.scalar(
            select(SandboxSessionModel).where(
                SandboxSessionModel.id == session_id,
                SandboxSessionModel.organization_id == organization_id,
            )
        )
        if row is None:
            raise SandboxError(f"No sandbox session {session_id}.")
        return row


async def destroy_session(session_id: UUID, organization_id: UUID) -> bool:
    row = await get_session(session_id, organization_id)
    if row.vendor_id is None:
        await _mark_destroyed(row.id)
        return True
    await release(_to_session(row), keep=False)
    return True


async def reap_orphans(organization_id: UUID) -> dict[str, int]:
    """Sweep each pinned config scope without touching another org's resources."""
    async with async_session_factory() as db:
        authorities = list(
            (
                await db.execute(
                    select(
                        SandboxSessionModel.sandbox_provider_config_id,
                        SandboxSessionModel.sandbox_provider_config_revision,
                    )
                    .where(
                        SandboxSessionModel.organization_id == organization_id,
                        SandboxSessionModel.state.in_(_LIVE_STATES),
                        SandboxSessionModel.deleted.is_(False),
                    )
                    .distinct()
                )
            ).all()
        )
    destroyed = 0
    for config_id, revision in authorities:
        adapter, _ = await _resolve_pinned_adapter(
            organization_id,
            provider_config_id=config_id,
            provider_config_revision=revision,
        )
        async with async_session_factory() as db:
            known = set(
                (
                    await db.execute(
                        select(SandboxSessionModel.vendor_id).where(
                            SandboxSessionModel.organization_id == organization_id,
                            SandboxSessionModel.sandbox_provider_config_id == config_id,
                            SandboxSessionModel.sandbox_provider_config_revision
                            == revision,
                            SandboxSessionModel.vendor_id.is_not(None),
                            SandboxSessionModel.state != SandboxState.DESTROYED,
                            SandboxSessionModel.deleted.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
        for vendor_id in await adapter.list_vendor_ids():
            if vendor_id not in known:
                await adapter.destroy_vendor_id(vendor_id)
                destroyed += 1
    return {"orphans_destroyed": destroyed}


async def _existing_run_session(
    db: AsyncSession,
    organization_id: UUID,
    agent_run_id: UUID | None,
) -> SandboxSessionModel | None:
    if agent_run_id is None:
        return None
    return await db.scalar(
        select(SandboxSessionModel).where(
            SandboxSessionModel.organization_id == organization_id,
            SandboxSessionModel.agent_run_id == agent_run_id,
            SandboxSessionModel.state == SandboxState.RUNNING,
            SandboxSessionModel.deleted.is_(False),
        )
    )


async def _active_grant(
    db: AsyncSession,
    organization_id: UUID,
    agent_id: UUID,
) -> SandboxGrantModel | None:
    return await db.scalar(
        select(SandboxGrantModel).where(
            SandboxGrantModel.organization_id == organization_id,
            SandboxGrantModel.agent_id == agent_id,
            SandboxGrantModel.deleted.is_(False),
        )
    )


async def _require_active_grant(
    db: AsyncSession,
    organization_id: UUID,
    agent_id: UUID | None,
) -> SandboxGrantModel:
    if agent_id is None:
        raise SandboxAccessError(
            "AgentRun sandbox acquisition requires an identified agent."
        )
    grant_row = await _active_grant(db, organization_id, agent_id)
    assert_can_run([grant_row] if grant_row is not None else [], agent_id)
    assert grant_row is not None
    if grant_row.access != SandboxAccess.RUN:
        raise SandboxAccessError(
            "The current sandbox grant does not permit code execution."
        )
    return grant_row


def _assert_grant_authorizes(
    grant_row: SandboxGrantModel,
    *,
    agent_id: UUID | None,
    grant_id: UUID | None,
    provider_config_id: UUID,
    provider_config_revision: int,
) -> None:
    if (
        not _same_identifier(grant_row.agent_id, agent_id)
        or not _same_identifier(grant_row.id, grant_id)
        or not _same_identifier(
            grant_row.sandbox_provider_config_id,
            provider_config_id,
        )
        or grant_row.sandbox_provider_config_revision != provider_config_revision
    ):
        raise SandboxAccessError(
            "The current sandbox grant does not authorize this workspace."
        )


def _same_identifier(left: object, right: object) -> bool:
    return left is not None and right is not None and str(left) == str(right)


async def _lock_capacity(
    db: AsyncSession,
    organization_id: UUID,
    agent_id: UUID | None,
    agent_run_id: UUID | None,
) -> None:
    keys = {_lock_key("organization", organization_id)}
    if agent_id is not None:
        keys.add(_lock_key("agent", agent_id))
    if agent_run_id is not None:
        keys.add(_lock_key("agent-run", agent_run_id))
    for key in sorted(keys):
        await db.execute(select(func.pg_advisory_xact_lock(key)))


async def _lock_agent_grant(db: AsyncSession, agent_id: UUID) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(_lock_key("agent", agent_id))))


def _lock_key(namespace: str, identifier: UUID) -> int:
    digest = hashlib.blake2b(
        f"sandbox:{namespace}:{identifier}".encode(),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


async def _assert_capacity(
    db,
    organization_id,
    agent_id,
    effective_policy: dict,
) -> None:
    organization_count = await db.scalar(
        select(func.count(SandboxSessionModel.id)).where(
            SandboxSessionModel.organization_id == organization_id,
            SandboxSessionModel.state.in_(_LIVE_STATES),
            SandboxSessionModel.deleted.is_(False),
        )
    )
    organization_limit = int(effective_policy["max_sessions"])
    if int(organization_count or 0) >= organization_limit:
        raise SandboxQuotaExceeded(
            "The organization's sandbox session ceiling has been reached."
        )
    if agent_id is None:
        return
    configured_agent_limit = effective_policy.get("grant_max_sessions")
    agent_limit = min(
        organization_limit,
        int(configured_agent_limit or organization_limit),
    )
    agent_count = await db.scalar(
        select(func.count(SandboxSessionModel.id)).where(
            SandboxSessionModel.organization_id == organization_id,
            SandboxSessionModel.agent_id == agent_id,
            SandboxSessionModel.state.in_(_LIVE_STATES),
            SandboxSessionModel.deleted.is_(False),
        )
    )
    if int(agent_count or 0) >= agent_limit:
        raise SandboxQuotaExceeded(
            "The agent's sandbox session ceiling has been reached."
        )


def _config_policy(resolved) -> dict[str, object]:
    return {
        **dict(resolved.config),
        "verified_image_id": resolved.verified_image_id,
        "network": False,
    }


def _effective_policy(
    resolved,
    *,
    grant_max_sessions: object = None,
) -> dict[str, object]:
    return {
        **_config_policy(resolved),
        "grant_max_sessions": grant_max_sessions,
    }


def _assert_checkpoint_matches_resolved(checkpoint, resolved) -> None:
    checkpoint_config_policy = dict(checkpoint.effective_policy)
    checkpoint_config_policy.pop("grant_max_sessions", None)
    if (
        resolved.verified_image_id != checkpoint.image
        or checkpoint_config_policy != _config_policy(resolved)
    ):
        raise SandboxError(
            "Pinned sandbox checkpoint authority no longer matches its config."
        )


async def _activate_reservation(
    organization_id: UUID,
    reservation_id: UUID,
    session: SandboxSession,
) -> None:
    async with async_session_factory() as db:
        row = await db.scalar(
            select(SandboxSessionModel).where(
                SandboxSessionModel.id == reservation_id,
                SandboxSessionModel.organization_id == organization_id,
                SandboxSessionModel.state == SandboxState.STARTING,
                SandboxSessionModel.deleted.is_(False),
            )
        )
        if row is None:
            raise SandboxError("Sandbox reservation disappeared before activation.")
        row.vendor_id = session.vendor_id
        row.state = SandboxState.RUNNING
        row.image = session.image
        row.workspace = session.workspace
        row.expires_at = session.expires_at
        row.last_used_at = arrow.utcnow().datetime
        await db.commit()


async def _retire_reservation(reservation_id: UUID) -> None:
    async with async_session_factory() as db:
        row = await db.get(SandboxSessionModel, reservation_id)
        if row is not None:
            row.state = SandboxState.DESTROYED
            row.deleted = True
            await db.commit()


async def _mark_destroyed(session_id: UUID) -> None:
    async with async_session_factory() as db:
        row = await db.get(SandboxSessionModel, session_id)
        if row is not None:
            row.state = SandboxState.DESTROYED
            row.deleted = True
            row.last_used_at = arrow.utcnow().datetime
            await db.commit()


async def _session_row(session_id: UUID) -> SandboxSessionModel:
    async with async_session_factory() as db:
        row = await db.get(SandboxSessionModel, session_id)
        if row is None:
            raise SandboxError(f"No sandbox session {session_id}.")
        return row


async def _resolve_pinned_adapter(
    organization_id: UUID,
    *,
    provider_config_id: UUID,
    provider_config_revision: int,
):
    """Resolve immutable sandbox authority within an owned DB session."""
    async with async_session_factory() as db:
        return await resolve_pinned_sandbox_adapter(
            organization_id,
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config_revision,
            db=db,
        )


async def _latest_checkpoint(
    db: AsyncSession,
    organization_id: UUID,
    agent_run_id: UUID | None,
) -> SandboxWorkspaceCheckpointModel | None:
    if agent_run_id is None:
        return None
    return await db.scalar(
        select(SandboxWorkspaceCheckpointModel)
        .where(
            SandboxWorkspaceCheckpointModel.organization_id == organization_id,
            SandboxWorkspaceCheckpointModel.agent_run_id == agent_run_id,
            SandboxWorkspaceCheckpointModel.deleted.is_(False),
        )
        .order_by(SandboxWorkspaceCheckpointModel.revision.desc())
        .limit(1)
    )
