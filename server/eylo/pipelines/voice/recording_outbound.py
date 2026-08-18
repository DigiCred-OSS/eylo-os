"""Durable outbound-attempt boundary for one recording track upload."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from absurd_sdk import AsyncTaskContext
from sqlalchemy import select

from eylo.common.contracts.storage import StorageLocator
from eylo.common.database import start_transaction
from eylo.common.outbound import (
    OutboundAttemptIdentity,
    OutboundAttemptSpec,
    OutboundAttemptState,
    OutboundOwnerKind,
    OutboundSendAuthorization,
    OutboundSendRetryable,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundTransportKind,
    fingerprint_outbound_input,
)
from eylo.durable_runtime import run_with_durable_heartbeat
from eylo.pipelines.outbound.durable_execution import (
    DurableStepContext,
    OutboundExecutionReceipt,
    execute_outbound_attempt,
)
from eylo.pipelines.outbound.models import OutboundAttemptModel
from eylo.pipelines.outbound.service import OutboundAttemptService
from eylo.pipelines.storage.runtime import StorageRuntime
from eylo.pipelines.voice.recording_storage import upload_recording_path
from eylo.sockets.storage.base import StorageOperationError

_TRACKS = frozenset({"user", "agent"})
_OBJECT_CONFLICT = "storage_object_conflict"
_OBJECT_MISSING = "storage_object_missing"
_DIGEST_UNAVAILABLE = "storage_digest_unavailable"
_INSPECTION_UNAVAILABLE = "storage_inspection_unavailable"
_RECONCILIATION_UNSUPPORTED = "storage_reconciliation_unsupported"


@dataclass(frozen=True, slots=True)
class RecordingTrackUploadResult:
    """Canonical outbound receipt plus its deterministic object locator."""

    track: str
    locator: StorageLocator
    receipt: OutboundExecutionReceipt

    def __post_init__(self) -> None:
        if self.track not in _TRACKS:
            raise ValueError("Recording upload track is invalid.")


@dataclass(frozen=True, slots=True)
class RecordingUploadCancellation:
    """What cancellation can honestly claim about already-started PUTs."""

    attempt_count: int
    may_have_external_effect: bool
    all_required_succeeded: bool


class RecordingAbsurdStepContext(DurableStepContext):
    """Adapt Absurd's positional step API to the shared outbound protocol."""

    def __init__(self, context: AsyncTaskContext) -> None:
        self._context = context

    async def step(self, *, key: str, version: int, operation):
        return await self._context.step(
            f"{key}:v{version}",
            lambda: run_with_durable_heartbeat(self._context, operation),
        )


async def execute_recording_track_upload(
    *,
    organization_id: UUID,
    recording_id: UUID,
    track: str,
    content: bytes,
    key: str,
    storage: StorageRuntime,
    context: DurableStepContext,
) -> RecordingTrackUploadResult:
    """Execute or recover one stable-key PUT without blind replay."""
    if track not in _TRACKS:
        raise ValueError("Recording upload track is invalid.")
    digest = hashlib.sha256(content).hexdigest()
    spec = _upload_spec(
        organization_id=organization_id,
        recording_id=recording_id,
        track=track,
        key=key,
        size=len(content),
        content_sha256=digest,
        storage=storage,
    )

    async def send(
        authorization: OutboundSendAuthorization,
    ) -> OutboundSendSucceeded | OutboundSendRetryable | OutboundSendTerminal:
        del authorization
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"eylo-recording-{track}-"
            ) as directory:
                path = Path(directory) / f"{track}.wav"
                await asyncio.to_thread(path.write_bytes, content)
                await upload_recording_path(
                    runtime=storage,
                    path=path,
                    key=key,
                    content_sha256=digest,
                )
        except StorageOperationError as error:
            if error.retryable and storage.adapter.capabilities.stable_key_put:
                return OutboundSendRetryable(failure_code="storage_retryable")
            return OutboundSendTerminal(failure_code="storage_rejected")
        return OutboundSendSucceeded()

    receipt = await execute_outbound_attempt(
        spec=spec,
        context=context,
        sender=send,
    )
    if receipt.state is OutboundAttemptState.UNKNOWN:
        receipt = await _reconcile_unknown(
            spec=spec,
            key=key,
            size=len(content),
            content_sha256=digest,
            storage=storage,
        )
    return RecordingTrackUploadResult(
        track=track,
        locator=storage.locate(key),
        receipt=receipt,
    )


async def cancel_recording_upload_attempts(
    *,
    organization_id: UUID,
    recording_id: UUID,
    required_track_count: int,
) -> RecordingUploadCancellation:
    """Fence unsent PUTs while preserving accepted/ambiguous effect truth."""
    async with start_transaction() as session:
        rows = list(
            (
                await session.scalars(
                    select(OutboundAttemptModel)
                    .where(
                        OutboundAttemptModel.organization_id == organization_id,
                        OutboundAttemptModel.owner_kind
                        == OutboundOwnerKind.VOICE_RECORDING.value,
                        OutboundAttemptModel.owner_id == recording_id,
                    )
                    .with_for_update()
                )
            ).all()
        )
        service = OutboundAttemptService(session)
        states = []
        for row in rows:
            cancelled = await service.request_cancel(
                organization_id=organization_id,
                attempt_id=UUID(str(row.id)),
            )
            states.append(cancelled.state)
    may_have_external_effect = any(
        state
        in {
            OutboundAttemptState.IN_FLIGHT,
            OutboundAttemptState.SUCCEEDED,
            OutboundAttemptState.UNKNOWN,
        }
        for state in states
    )
    return RecordingUploadCancellation(
        attempt_count=len(states),
        may_have_external_effect=may_have_external_effect,
        all_required_succeeded=(
            required_track_count > 0
            and len(states) == required_track_count
            and all(state is OutboundAttemptState.SUCCEEDED for state in states)
        ),
    )


def _upload_spec(
    *,
    organization_id: UUID,
    recording_id: UUID,
    track: str,
    key: str,
    size: int,
    content_sha256: str,
    storage: StorageRuntime,
) -> OutboundAttemptSpec:
    authority = storage.authority
    identity = OutboundAttemptIdentity(
        organization_id=organization_id,
        owner_kind=OutboundOwnerKind.VOICE_RECORDING,
        owner_id=recording_id,
        operation_key=f"storage.upload.{track}",
    )
    return OutboundAttemptSpec(
        identity=identity,
        provider_operation="storage.object.put",
        transport_kind=OutboundTransportKind.OBJECT_STORAGE,
        destination_origin=(
            f"storage://{authority.provider}/{authority.organization_id}/"
            f"{authority.provider_config_id}@{authority.provider_config_revision}/"
            f"{authority.fingerprint}"
        ),
        request_fingerprint=fingerprint_outbound_input(
            {
                "authority": authority.to_dict(),
                "content_sha256": content_sha256,
                "key": key,
                "size": size,
                "track": track,
            }
        ),
    )


async def _reconcile_unknown(
    *,
    spec: OutboundAttemptSpec,
    key: str,
    size: int,
    content_sha256: str,
    storage: StorageRuntime,
) -> OutboundExecutionReceipt:
    capabilities = storage.adapter.capabilities
    if not capabilities.put_reconciliation:
        return await _record_reconciliation(
            spec,
            state=OutboundAttemptState.UNKNOWN,
            failure_code=_RECONCILIATION_UNSUPPORTED,
        )
    try:
        observed = await storage.adapter.inspect_object(key)
    except StorageOperationError:
        return await _record_reconciliation(
            spec,
            state=OutboundAttemptState.UNKNOWN,
            failure_code=_INSPECTION_UNAVAILABLE,
        )
    if observed is None:
        return await _record_reconciliation(
            spec,
            state=OutboundAttemptState.UNKNOWN,
            failure_code=_OBJECT_MISSING,
        )
    if observed.content_sha256 is None:
        return await _record_reconciliation(
            spec,
            state=OutboundAttemptState.UNKNOWN,
            failure_code=_DIGEST_UNAVAILABLE,
        )
    if observed.size != size or observed.content_sha256 != content_sha256:
        return await _record_reconciliation(
            spec,
            state=OutboundAttemptState.TERMINAL,
            failure_code=_OBJECT_CONFLICT,
        )
    return await _record_reconciliation(
        spec,
        state=OutboundAttemptState.SUCCEEDED,
        failure_code=None,
    )


async def _record_reconciliation(
    spec: OutboundAttemptSpec,
    *,
    state: OutboundAttemptState,
    failure_code: str | None,
) -> OutboundExecutionReceipt:
    async with start_transaction() as session:
        service = OutboundAttemptService(session)
        row = await service.get(
            organization_id=spec.identity.organization_id,
            attempt_id=spec.identity.attempt_id,
            for_update=True,
        )
        if row.state is OutboundAttemptState.UNKNOWN:
            row = await service.reconcile(
                organization_id=spec.identity.organization_id,
                attempt_id=spec.identity.attempt_id,
                state=state,
                failure_code=failure_code,
            )
        return OutboundExecutionReceipt.from_model(row)


__all__ = [
    "RecordingAbsurdStepContext",
    "RecordingTrackUploadResult",
    "RecordingUploadCancellation",
    "cancel_recording_upload_attempts",
    "execute_recording_track_upload",
]
