"""Non-blocking audio recorder that spills normalized PCM tracks to disk.

Captures both user (inbound) and agent (outbound/TTS) audio tracks during a
voice session. Chunks are normalized to PCM S16LE as they arrive, written to
temporary files, and converted to WAV only at finalize time before upload.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import tempfile
import wave
from pathlib import Path
from uuid import UUID

import arrow
import uuid_utils
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.voice_transcripts.models import VoiceSessionModel

logger = logging.getLogger(__name__)


_PCM_ENCODINGS = {
    "linear16",
    "pcm",
    "pcm16",
    "pcm_linear16",
    "pcm_s16le",
    "s16le",
}
_MULAW_ENCODINGS = {
    "mulaw",
    "pcm_mulaw",
    "pcm_ulaw",
    "ulaw",
    "g711_ulaw",
    "g711-ulaw",
    "audio/x-mulaw",
}
_PCM_SAMPLE_WIDTH = 2


def _normalize_encoding(encoding: str | None) -> str:
    if not encoding:
        return "pcm_s16le"
    return encoding.strip().lower()


def _is_supported_recording_encoding(encoding: str | None) -> bool:
    normalized_encoding = _normalize_encoding(encoding)
    return (
        normalized_encoding in _PCM_ENCODINGS or normalized_encoding in _MULAW_ENCODINGS
    )


def _decode_mulaw_to_pcm_s16le(audio_data: bytes) -> bytes:
    """Decode μ-law bytes to PCM S16LE bytes."""
    pcm_data = bytearray(len(audio_data) * 2)

    for index, byte in enumerate(audio_data):
        mu_law = (~byte) & 0xFF
        magnitude = ((mu_law & 0x0F) << 3) + 0x84
        magnitude <<= (mu_law & 0x70) >> 4
        sample = 0x84 - magnitude if mu_law & 0x80 else magnitude - 0x84

        offset = index * 2
        pcm_data[offset : offset + 2] = int(sample).to_bytes(
            2, byteorder="little", signed=True
        )

    return bytes(pcm_data)


def _normalize_audio_chunk(audio_bytes: bytes, encoding: str | None) -> bytes:
    """Normalize an input audio chunk to PCM S16LE."""
    normalized_encoding = _normalize_encoding(encoding)
    if normalized_encoding in _PCM_ENCODINGS:
        return audio_bytes
    if normalized_encoding in _MULAW_ENCODINGS:
        return _decode_mulaw_to_pcm_s16le(audio_bytes)
    raise ValueError(f"Unsupported recording encoding: {encoding}")


def build_recording_base_path(
    *,
    conversation_id: UUID,
    session_id: str,
    started_at,
    recording_id: UUID,
) -> str:
    """Build one collision-safe, inspectable key prefix for a recording row."""
    timestamp = started_at.format("YYYYMMDD_HHmmss")
    session_fingerprint = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return (
        f"recordings/{conversation_id}/"
        f"{timestamp}_{session_fingerprint}/{recording_id}"
    )


class AudioRecorder:
    """Per-session audio recorder with separate user/agent tracks."""

    def __init__(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        voice_session_id: UUID | None = None,
        telephony_call_id: UUID | None = None,
        storage_provider_config_id: UUID | None = None,
        storage_provider_config_revision: int | None = None,
        user_sample_rate: int = 16000,
        agent_sample_rate: int = 16000,
        user_encoding: str = "pcm_s16le",
        agent_encoding: str = "pcm_s16le",
        channels: int = 1,
    ):
        self._organization_id = organization_id
        self._conversation_id = conversation_id
        self._session_id = session_id
        self._voice_session_id = voice_session_id
        self._telephony_call_id = telephony_call_id
        self._storage_provider_config_id = storage_provider_config_id
        self._storage_provider_config_revision = storage_provider_config_revision
        self._user_sample_rate = user_sample_rate
        self._agent_sample_rate = agent_sample_rate
        self._user_encoding = _normalize_encoding(user_encoding)
        self._agent_encoding = _normalize_encoding(agent_encoding)
        self._channels = channels
        unsupported_tracks = self._unsupported_tracks()
        self._recording_failure = (
            "Recording encoding is unsupported." if unsupported_tracks else None
        )
        self._user_recording_enabled = not unsupported_tracks
        self._agent_recording_enabled = not unsupported_tracks
        if unsupported_tracks:
            logger.warning(
                "Voice recording disabled before capture organization_id=%s: "
                "unsupported tracks=%s",
                self._organization_id,
                ",".join(unsupported_tracks),
            )

        self._temp_dir = Path(tempfile.mkdtemp(prefix="eylo-recording-"))
        self._user_pcm_path = self._temp_dir / "user.pcm"
        self._agent_pcm_path = self._temp_dir / "agent.pcm"
        self._user_wav_path = self._temp_dir / "user.wav"
        self._agent_wav_path = self._temp_dir / "agent.wav"

        self._user_bytes_written = 0
        self._agent_bytes_written = 0
        self._started_at = arrow.utcnow()
        self._finalized = False

    @property
    def has_user_audio(self) -> bool:
        return self._user_bytes_written > 0

    @property
    def has_agent_audio(self) -> bool:
        return self._agent_bytes_written > 0

    @property
    def user_duration_seconds(self) -> float:
        bytes_per_second = self._user_sample_rate * self._channels * _PCM_SAMPLE_WIDTH
        return self._user_bytes_written / bytes_per_second if bytes_per_second else 0

    @property
    def agent_duration_seconds(self) -> float:
        bytes_per_second = self._agent_sample_rate * self._channels * _PCM_SAMPLE_WIDTH
        return self._agent_bytes_written / bytes_per_second if bytes_per_second else 0

    def set_user_audio_format(
        self, *, sample_rate: int, encoding: str = "pcm_s16le"
    ) -> None:
        """Set the effective user track format before user PCM is recorded.

        Browser/WebRTC input is commonly captured at 44.1/48kHz, then
        downsampled before this recorder sees it. The WAV header must describe
        the post-processed bytes, not the microphone source format.
        """
        normalized_encoding = _normalize_encoding(encoding)
        if self._user_bytes_written > 0:
            if (
                sample_rate != self._user_sample_rate
                or normalized_encoding != self._user_encoding
            ):
                logger.warning(
                    "Ignoring user recording format change organization_id=%s after "
                    "audio was already written (current=%dHz/%s, requested=%dHz/%s)",
                    self._organization_id,
                    self._user_sample_rate,
                    self._user_encoding,
                    sample_rate,
                    normalized_encoding,
                )
            return

        self._user_sample_rate = sample_rate
        self._user_encoding = normalized_encoding
        if not _is_supported_recording_encoding(self._user_encoding):
            self._mark_recording_failure("Recording encoding is unsupported.")

    def bind_voice_session(
        self,
        *,
        voice_session_id: UUID,
        telephony_call_id: UUID | None,
    ) -> None:
        """Bind capture to its exact durable owner before any upload is filed."""
        if self._finalized:
            return
        if (
            self._voice_session_id is not None
            and self._voice_session_id != voice_session_id
        ) or (
            self._telephony_call_id is not None
            and self._telephony_call_id != telephony_call_id
        ):
            self._mark_recording_failure("Recording owner authority is inconsistent.")
            return
        self._voice_session_id = voice_session_id
        self._telephony_call_id = telephony_call_id

    def record_user(self, audio_bytes: bytes) -> None:
        if self._finalized or not audio_bytes or not self._user_recording_enabled:
            return
        self._append_pcm_chunk(
            self._user_pcm_path,
            audio_bytes,
            encoding=self._user_encoding,
            is_user=True,
        )

    def record_agent(self, audio_bytes: bytes) -> None:
        if self._finalized or not audio_bytes or not self._agent_recording_enabled:
            return
        self._append_pcm_chunk(
            self._agent_pcm_path,
            audio_bytes,
            encoding=self._agent_encoding,
            is_user=False,
        )

    async def finalize(self) -> None:
        """Commit captured audio for durable upload without failing call teardown."""
        if self._finalized:
            return
        self._finalized = True

        if self._recording_failure is not None:
            await self._record_filing_failure(
                self._recording_failure,
                recording_id=UUID(str(uuid_utils.uuid7())),
            )
            self._cleanup_temp_files()
            return

        if not self.has_user_audio and not self.has_agent_audio:
            self._cleanup_temp_files()
            logger.debug(
                "No audio recorded organization_id=%s; skipping upload",
                self._organization_id,
            )
            return

        await self._file_upload()

    def _append_pcm_chunk(
        self,
        path: Path,
        audio_bytes: bytes,
        *,
        encoding: str,
        is_user: bool,
    ) -> None:
        try:
            pcm_chunk = _normalize_audio_chunk(audio_bytes, encoding)
        except ValueError:
            logger.warning(
                "Voice recording disabled during %s-track normalization for "
                "organization_id=%s.",
                "user" if is_user else "agent",
                self._organization_id,
            )
            self._mark_recording_failure("Recording encoding is unsupported.")
            return

        with path.open("ab") as handle:
            handle.write(pcm_chunk)

        if is_user:
            self._user_bytes_written += len(pcm_chunk)
        else:
            self._agent_bytes_written += len(pcm_chunk)

    async def _file_upload(self) -> None:
        """Encode locally, commit bytes to PostgreSQL, then nudge Absurd."""
        recording_id = UUID(str(uuid_utils.uuid7()))
        try:
            from eylo.common.database import start_transaction
            from eylo.modules.voice.recording.service import VoiceRecordingService

            base_path = build_recording_base_path(
                conversation_id=self._conversation_id,
                session_id=self._session_id,
                started_at=self._started_at,
                recording_id=recording_id,
            )
            if (
                self._storage_provider_config_id is None
                or self._storage_provider_config_revision is None
            ):
                raise NotConfiguredError(
                    capability=Capability.STORAGE,
                    missing=["provider_config", "provider_config_revision"],
                    configure_via="/api/storage-configs",
                )
            if self._voice_session_id is None:
                raise ValueError("Recording owner authority is unavailable.")
            user_wav = None
            agent_wav = None
            user_key = f"{base_path}/user.wav" if self.has_user_audio else None
            agent_key = f"{base_path}/agent.wav" if self.has_agent_audio else None
            if self.has_user_audio:
                await asyncio.to_thread(
                    self._write_wav_file,
                    pcm_path=self._user_pcm_path,
                    wav_path=self._user_wav_path,
                    sample_rate=self._user_sample_rate,
                )
                user_wav = await asyncio.to_thread(
                    self._user_wav_path.read_bytes,
                )

            if self.has_agent_audio:
                await asyncio.to_thread(
                    self._write_wav_file,
                    pcm_path=self._agent_pcm_path,
                    wav_path=self._agent_wav_path,
                    sample_rate=self._agent_sample_rate,
                )
                agent_wav = await asyncio.to_thread(
                    self._agent_wav_path.read_bytes,
                )

            async with start_transaction() as db_session:
                await VoiceRecordingService().file_upload(
                    recording_id=recording_id,
                    organization_id=self._organization_id,
                    conversation_id=self._conversation_id,
                    session_id=self._session_id,
                    voice_session_id=self._voice_session_id,
                    telephony_call_id=self._telephony_call_id,
                    storage_provider_config_id=self._storage_provider_config_id,
                    storage_provider_config_revision=(
                        self._storage_provider_config_revision
                    ),
                    user_wav=user_wav,
                    agent_wav=agent_wav,
                    user_storage_key=user_key,
                    agent_storage_key=agent_key,
                    user_duration_seconds=self.user_duration_seconds,
                    agent_duration_seconds=self.agent_duration_seconds,
                    user_sample_rate=self._user_sample_rate,
                    agent_sample_rate=self._agent_sample_rate,
                )
                await _file_recording_session_fact(
                    db_session,
                    organization_id=self._organization_id,
                    voice_session_id=self._voice_session_id,
                    recording_id=recording_id,
                    conversation_id=self._conversation_id,
                    event_type="voice.recording.queued",
                )

            from eylo.pipelines.voice.recording_durable_execution import (
                spawn_voice_recording_upload,
            )

            try:
                await spawn_voice_recording_upload(
                    organization_id=self._organization_id,
                    recording_id=recording_id,
                )
            except Exception as error:
                logger.error(
                    "Recording %s filed; direct durable spawn will be retried "
                    "by outbox. error_type=%s",
                    recording_id,
                    type(error).__name__,
                )
        except NotConfiguredError:
            await self._record_filing_failure(
                "Storage is not configured for recording.",
                recording_id=recording_id,
            )
        except Exception:
            await self._record_filing_failure(
                "Recording could not be staged for upload.",
                recording_id=recording_id,
            )
        finally:
            self._cleanup_temp_files()

    async def _record_filing_failure(
        self,
        reason: str,
        *,
        recording_id: UUID,
    ) -> None:
        """Persist why durable filing failed; never raise into the voice flow."""
        logger.error(
            "Voice recording filing failed organization_id=%s",
            self._organization_id,
        )

        if self._voice_session_id is None:
            logger.error(
                "Recording failure state could not be filed organization_id=%s: "
                "owner authority is unavailable.",
                self._organization_id,
            )
            return

        try:
            from eylo.common.database import start_transaction
            from eylo.modules.voice.recording.service import VoiceRecordingService

            async with start_transaction() as db:
                await VoiceRecordingService().record_unavailable_upload(
                    recording_id=recording_id,
                    organization_id=self._organization_id,
                    conversation_id=self._conversation_id,
                    session_id=self._session_id,
                    voice_session_id=self._voice_session_id,
                    telephony_call_id=self._telephony_call_id,
                    reason=reason,
                    user_duration_seconds=self.user_duration_seconds,
                    agent_duration_seconds=self.agent_duration_seconds,
                    user_sample_rate=self._user_sample_rate,
                    agent_sample_rate=self._agent_sample_rate,
                )
                await _file_recording_session_fact(
                    db,
                    organization_id=self._organization_id,
                    voice_session_id=self._voice_session_id,
                    recording_id=recording_id,
                    conversation_id=self._conversation_id,
                    event_type="voice.recording.failed",
                    payload={"reason": "filing_failed"},
                )

                session = await db.scalar(
                    select(VoiceSessionModel).where(
                        VoiceSessionModel.organization_id == self._organization_id,
                        VoiceSessionModel.session_id == self._session_id,
                    )
                )
                if session is not None:
                    session.meta = {
                        **(session.meta or {}),
                        "recording_upload_error": reason,
                    }
        except Exception as error:
            # Recording the failure must not itself become an unhandled
            # failure in a detached task.
            logger.error(
                "Could not persist the recording filing failure organization_id=%s "
                "error_type=%s",
                self._organization_id,
                type(error).__name__,
            )

    def _write_wav_file(
        self, *, pcm_path: Path, wav_path: Path, sample_rate: int
    ) -> None:
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(self._channels)
            wav_file.setsampwidth(_PCM_SAMPLE_WIDTH)
            wav_file.setframerate(sample_rate)
            with pcm_path.open("rb") as pcm_file:
                while chunk := pcm_file.read(64 * 1024):
                    wav_file.writeframesraw(chunk)

    def _unsupported_tracks(self) -> list[str]:
        return [
            track
            for track, encoding in (
                ("user", self._user_encoding),
                ("agent", self._agent_encoding),
            )
            if not _is_supported_recording_encoding(encoding)
        ]

    def _mark_recording_failure(self, reason: str) -> None:
        self._recording_failure = reason
        self._user_recording_enabled = False
        self._agent_recording_enabled = False

    def _cleanup_temp_files(self) -> None:
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)


async def _file_recording_session_fact(
    db: AsyncSession,
    *,
    organization_id: UUID,
    voice_session_id: UUID,
    recording_id: UUID,
    conversation_id: UUID,
    event_type: str,
    payload: dict | None = None,
) -> None:
    voice_session = await db.scalar(
        select(VoiceSessionModel).where(
            VoiceSessionModel.id == voice_session_id,
            VoiceSessionModel.organization_id == organization_id,
            VoiceSessionModel.conversation_id == conversation_id,
            VoiceSessionModel.deleted.is_(False),
        )
    )
    if voice_session is None or voice_session.user_session_id is None:
        return
    await file_user_session_fact(
        db,
        organization_id=organization_id,
        user_session_id=voice_session.user_session_id,
        subject_type="voice.recording",
        subject_id=recording_id,
        event_type=event_type,
        payload={
            "conversation_id": str(conversation_id),
            "voice_session_id": str(voice_session_id),
            **(payload or {}),
        },
    )
