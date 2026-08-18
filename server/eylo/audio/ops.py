"""Audio sampling, buffering, and mixing primitives."""

from __future__ import annotations

from collections import deque

import numpy as np
import soxr

# ---------------------------------------------------------------------------
# Constants — pre-allocated frames for hot-path reuse
# ---------------------------------------------------------------------------

# 20 ms of silence at 16 kHz mono int16 (320 samples × 2 bytes = 640 bytes).
# Callers should use `.copy()` only if they mutate the array; read-only
# consumers (e.g. AudioFrame.from_ndarray which copies internally) can
# pass the constant directly.
SILENCE_FRAME_16K_20MS: np.ndarray = np.zeros(320, dtype=np.int16)


# ---------------------------------------------------------------------------
# Silence / energy detection
# ---------------------------------------------------------------------------


def is_silent(audio_data: bytes) -> bool:
    """Return True if every byte in *audio_data* is zero.

    Uses the built-in ``any()`` on a ``bytes`` object which iterates in C
    (via ``PyObject_IsTrue`` on each byte), ~50× faster than the equivalent
    ``all(byte == 0 for byte in audio_data)`` generator expression.
    """
    return not any(audio_data)


def is_low_energy(
    audio_data: bytes,
    *,
    threshold_rms: float = 50.0,
) -> bool:
    """Return True if the RMS energy of PCM16 audio is below *threshold_rms*.

    Args:
        audio_data: Raw PCM 16-bit signed little-endian bytes.
        threshold_rms: RMS amplitude below which audio is considered
            low-energy.  Range is 0–32768 (int16 scale).  Default 50
            catches near-silence without flagging soft speech.

    """
    samples = np.frombuffer(audio_data, dtype=np.int16)
    if len(samples) == 0:
        return True
    rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
    return float(rms) < threshold_rms


# ---------------------------------------------------------------------------
# Streaming PCM16 resampler with cached FIR filter
# ---------------------------------------------------------------------------


class StreamingResampler:
    """Streaming PCM16 mono resampler backed by libsoxr (C library).

    Uses ``soxr.ResampleStream`` which:
      - Runs resampling in native C (~5–10× faster than scipy)
      - Maintains cross-chunk state (overlap buffer) for artifact-free
        streaming — no clicks or discontinuities at chunk boundaries
      - Accepts and returns int16 directly (no float64 intermediates)

    This is the same approach used by Pipecat (Daily) and LiveKit Agents
    for production real-time voice pipelines.

    Usage::

        resampler = StreamingResampler(from_rate=24000, to_rate=16000)
        pcm16k = resampler.process(pcm24k_chunk)
    """

    __slots__ = ("_stream", "_from_rate", "_to_rate")

    def __init__(self, from_rate: int, to_rate: int) -> None:
        self._from_rate = from_rate
        self._to_rate = to_rate
        self._stream = soxr.ResampleStream(
            from_rate,
            to_rate,
            num_channels=1,
            dtype="int16",
        )

    def process(self, audio: bytes) -> bytes:
        """Resample a PCM16 mono chunk.  Returns resampled PCM16 bytes."""
        if not audio:
            return audio
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return audio
        resampled = self._stream.resample_chunk(samples)
        return resampled.tobytes()

    def reset(self) -> None:
        """Reset internal state.  Call between unrelated audio streams."""
        self._stream = soxr.ResampleStream(
            self._from_rate,
            self._to_rate,
            num_channels=1,
            dtype="int16",
        )


# ---------------------------------------------------------------------------
# O(1) amortized audio chunk buffer
# ---------------------------------------------------------------------------


class AudioChunkBuffer:
    """Deque-backed audio byte buffer with O(1) amortized frame extraction.

    Replaces the common ``bytearray`` pattern::

        frame = bytes(buf[:N])
        buf = buf[N:]          # ← O(remaining) — copies ALL leftover bytes

    With a deque of immutable ``bytes`` objects where ``read()`` pops from
    the front without copying the tail.

    Thread safety: **not** thread-safe.  Wrap calls with the same
    ``asyncio.Lock`` the caller already holds (see ``OutgoingAudioTrack``).
    """

    __slots__ = ("_chunks", "_offset", "_total")

    def __init__(self) -> None:
        self._chunks: deque[bytes] = deque()
        self._offset: int = 0  # byte offset into the first chunk
        self._total: int = 0

    # -- Write side --

    def write(self, data: bytes) -> None:
        """Append *data* to the buffer.  O(1)."""
        if data:
            self._chunks.append(data)
            self._total += len(data)

    # -- Read side --

    @property
    def available(self) -> int:
        """Number of unread bytes in the buffer."""
        return self._total

    def read(self, n: int) -> bytes | None:
        """Extract exactly *n* bytes, or ``None`` if fewer are available.

        Amortised O(1) — each byte is copied at most twice (into the deque
        on write, out of it on read).  The old bytearray pattern copied the
        entire remaining buffer on every read.
        """
        if self._total < n:
            return None

        parts: list[bytes] = []
        remaining = n

        while remaining > 0:
            chunk = self._chunks[0]
            avail = len(chunk) - self._offset

            if avail <= remaining:
                # Consume the rest of this chunk
                parts.append(chunk[self._offset :] if self._offset else chunk)
                self._chunks.popleft()
                self._offset = 0
                remaining -= avail
            else:
                # Partial read from current chunk
                parts.append(chunk[self._offset : self._offset + remaining])
                self._offset += remaining
                remaining = 0

        self._total -= n
        return b"".join(parts) if len(parts) > 1 else parts[0]

    def clear(self) -> None:
        """Discard all buffered data.  O(1)."""
        self._chunks.clear()
        self._offset = 0
        self._total = 0


# ---------------------------------------------------------------------------
# Ambient noise generator
# ---------------------------------------------------------------------------


def generate_brown_noise(
    duration_s: float,
    sample_rate: int,
    *,
    amplitude: int = 50,
    seed: int = 42,
) -> np.ndarray:
    """Generate low-amplitude brown noise (int16) for comfort/ambient use.

    Brown noise (cumulative sum of white noise) sounds like a soft
    air-conditioner hum — natural and non-distracting.

    Args:
        duration_s: Length in seconds.
        sample_rate: Output sample rate (e.g. 16000).
        amplitude: Peak amplitude in int16 range (0–32768).  Default 50
            is intentionally very quiet.
        seed: RNG seed for reproducibility.

    Returns:
        ``np.ndarray`` of dtype ``int16`` with ``int(duration_s * sample_rate)``
        samples.

    """
    n_samples = int(duration_s * sample_rate)
    rng = np.random.default_rng(seed=seed)
    white = rng.standard_normal(n_samples)
    brown = np.cumsum(white)
    peak = np.max(np.abs(brown)) or 1.0
    return (brown / peak * amplitude).astype(np.int16)


# ---------------------------------------------------------------------------
# AudioSampler — unified high-performance audio processor
# ---------------------------------------------------------------------------

# Shared pre-computed constants for dBFS and energy calculations.
_INT16_MAX_F32 = np.float32(32768.0)
_DBFS_FLOOR = np.float32(-96.0)  # ~ 20*log10(1/32768)


class AudioSampler:
    """High-performance audio processor for PCM16 mono streams."""

    __slots__ = ("_sample_rate", "_resamplers")

    def __init__(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        # Lazily populated: (from_rate, to_rate) → StreamingResampler
        self._resamplers: dict[tuple[int, int], StreamingResampler] = {}

    # -- properties ----------------------------------------------------------

    @property
    def sample_rate(self) -> int:
        """The native sample rate this sampler was created for."""
        return self._sample_rate

    # -- silence / energy detection ------------------------------------------

    @staticmethod
    def is_silent(audio: bytes) -> bool:
        """Return ``True`` if every byte is zero.

        Delegates to C-level ``any()`` on a ``bytes`` object — roughly
        50× faster than a Python generator comprehension.
        """
        return not any(audio)

    @staticmethod
    def rms(audio: bytes) -> float:
        """Root-mean-square amplitude of PCM16 audio.

        Returns 0.0 for empty input.  The computation stays in float32 to
        avoid int16 overflow on squaring (32767² > 2³¹).
        """
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

    @staticmethod
    def peak(audio: bytes) -> int:
        """Peak absolute sample value in PCM16 audio.

        Returns 0 for empty input.  Uses float32 to avoid the int16
        overflow trap: ``np.abs(np.int16(-32768))`` wraps back to −32768.
        """
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return 0
        return int(np.max(np.abs(samples.astype(np.float32))))

    @staticmethod
    def dbfs(audio: bytes) -> float:
        """Peak level in dBFS (decibels relative to full scale).

        Returns ``-96.0`` (the int16 noise floor) for empty or silent
        input.  Full-scale (±32768) returns ``0.0``.
        """
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return float(_DBFS_FLOOR)
        peak_abs = np.max(np.abs(samples.astype(np.float32)))
        if peak_abs == 0.0:
            return float(_DBFS_FLOOR)
        return float(np.float32(20.0) * np.log10(peak_abs / _INT16_MAX_F32))

    @staticmethod
    def is_low_energy(audio: bytes, *, threshold_rms: float = 50.0) -> bool:
        """Return ``True`` if RMS amplitude is below *threshold_rms*.

        Args:
            audio: Raw PCM16 mono bytes.
            threshold_rms: RMS amplitude below which audio is considered
                low-energy.  Range 0–32768.  Default 50 catches near-silence
                without flagging soft speech.

        """
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return True
        rms_val = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
        return float(rms_val) < threshold_rms

    @staticmethod
    def energy_ratio(audio: bytes, *, threshold: float = 0.01) -> float:
        """Fraction of samples whose absolute normalised value ≥ *threshold*.

        Returns a value in ``[0.0, 1.0]``.  Useful for estimating how
        much of a chunk contains audible signal vs near-silence.

        Args:
            audio: Raw PCM16 mono bytes.
            threshold: Normalised amplitude threshold in [0.0, 1.0].
                Default 0.01 (~−40 dBFS) separates signal from noise floor.

        """
        samples = np.frombuffer(audio, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        normalised = np.abs(samples.astype(np.float32)) / _INT16_MAX_F32
        return float(np.mean(normalised >= threshold))

    # -- resampling ----------------------------------------------------------

    def _get_resampler(self, from_rate: int, to_rate: int) -> StreamingResampler:
        """Return a cached ``StreamingResampler`` for the given rate pair."""
        key = (from_rate, to_rate)
        resampler = self._resamplers.get(key)
        if resampler is None:
            resampler = StreamingResampler(from_rate=from_rate, to_rate=to_rate)
            self._resamplers[key] = resampler
        return resampler

    def downsample(self, audio: bytes, *, to_rate: int) -> bytes:
        """Resample PCM16 mono audio from *sample_rate* down to *to_rate*.

        The underlying ``soxr.ResampleStream`` maintains cross-chunk state
        so calling this repeatedly on consecutive chunks produces
        artifact-free output (no clicks at boundaries).

        Args:
            audio: Raw PCM16 mono bytes at ``self.sample_rate``.
            to_rate: Target sample rate.  Must be ≤ ``self.sample_rate``.

        Raises:
            ValueError: If *to_rate* > ``self.sample_rate``.

        """
        if to_rate > self._sample_rate:
            raise ValueError(
                f"downsample requires to_rate ({to_rate}) "
                f"<= sample_rate ({self._sample_rate})"
            )
        if to_rate == self._sample_rate:
            return audio
        return self._get_resampler(self._sample_rate, to_rate).process(audio)

    def upsample(self, audio: bytes, *, to_rate: int) -> bytes:
        """Resample PCM16 mono audio from *sample_rate* up to *to_rate*.

        Args:
            audio: Raw PCM16 mono bytes at ``self.sample_rate``.
            to_rate: Target sample rate.  Must be ≥ ``self.sample_rate``.

        Raises:
            ValueError: If *to_rate* < ``self.sample_rate``.

        """
        if to_rate < self._sample_rate:
            raise ValueError(
                f"upsample requires to_rate ({to_rate}) "
                f">= sample_rate ({self._sample_rate})"
            )
        if to_rate == self._sample_rate:
            return audio
        return self._get_resampler(self._sample_rate, to_rate).process(audio)

    def resample(self, audio: bytes, *, to_rate: int) -> bytes:
        """Resample PCM16 mono audio to an arbitrary *to_rate*.

        Convenience wrapper — delegates to ``downsample`` or ``upsample``
        depending on the direction, or returns the input unchanged when
        rates match.
        """
        if to_rate == self._sample_rate:
            return audio
        if to_rate < self._sample_rate:
            return self.downsample(audio, to_rate=to_rate)
        return self.upsample(audio, to_rate=to_rate)

    def reset(self) -> None:
        """Reset all cached resampler state.

        Call this when switching between unrelated audio streams to avoid
        overlap artefacts from the previous stream bleeding into the new one.
        """
        for resampler in self._resamplers.values():
            resampler.reset()


# ---------------------------------------------------------------------------
# AudioBuffer — sample-rate-aware accumulator with fixed-frame extraction
# ---------------------------------------------------------------------------


class AudioBuffer:
    """Sample-rate-aware PCM16 mono byte buffer with fixed-frame extraction."""

    __slots__ = (
        "_inner",
        "_sample_rate",
        "_frame_bytes",
        "_frame_samples",
        "_max_bytes",
        "_total_samples_written",
    )

    def __init__(
        self,
        sample_rate: int,
        frame_duration_ms: int = 20,
        *,
        max_duration_ms: int | None = None,
    ) -> None:
        """Args:
        sample_rate: Audio sample rate in Hz (e.g. 16000, 24000).
        frame_duration_ms: Duration of each extracted frame in
            milliseconds.  Default 20 ms (the standard WebRTC/voice
            frame size).
        max_duration_ms: Optional capacity cap in milliseconds.  When
            set, :meth:`write` silently drops the oldest bytes to stay
            within this limit.  ``None`` means unlimited.

        """
        self._inner = AudioChunkBuffer()
        self._sample_rate = sample_rate
        self._frame_samples = sample_rate * frame_duration_ms // 1000
        self._frame_bytes = self._frame_samples * 2  # int16 = 2 bytes
        self._total_samples_written: int = 0

        if max_duration_ms is not None:
            max_samples = sample_rate * max_duration_ms // 1000
            self._max_bytes: int | None = max_samples * 2
        else:
            self._max_bytes = None

    # -- properties ----------------------------------------------------------

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def frame_bytes(self) -> int:
        """Size of one frame in bytes."""
        return self._frame_bytes

    @property
    def frame_samples(self) -> int:
        """Number of PCM16 samples in one frame."""
        return self._frame_samples

    @property
    def available_bytes(self) -> int:
        """Unread bytes currently buffered."""
        return self._inner.available

    @property
    def available_samples(self) -> int:
        """Unread PCM16 samples currently buffered."""
        return self._inner.available // 2

    @property
    def duration_s(self) -> float:
        """Duration of buffered audio in seconds."""
        return self.available_samples / self._sample_rate

    @property
    def frame_count(self) -> int:
        """Number of complete frames available for reading."""
        return self._inner.available // self._frame_bytes

    @property
    def total_samples_written(self) -> int:
        """Cumulative samples written since creation or last clear."""
        return self._total_samples_written

    # -- write side ----------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Append *data* to the buffer.

        If *max_duration_ms* was set and the buffer would exceed capacity,
        the oldest bytes are silently discarded first.
        """
        if not data:
            return

        self._total_samples_written += len(data) // 2
        self._inner.write(data)

        if self._max_bytes is not None:
            overflow = self._inner.available - self._max_bytes
            if overflow > 0:
                # Discard oldest bytes to stay within capacity.
                # Align to 2-byte (int16 sample) boundary.
                discard = overflow + (overflow % 2)
                self._inner.read(discard)

    # -- read side -----------------------------------------------------------

    def read_frames(self) -> list[bytes]:
        """Extract all complete fixed-duration frames.

        Returns a (possibly empty) list of ``bytes`` objects, each exactly
        :attr:`frame_bytes` long.  Leftover bytes shorter than one frame
        remain in the buffer for the next call.
        """
        frames: list[bytes] = []
        while self._inner.available >= self._frame_bytes:
            frame = self._inner.read(self._frame_bytes)
            if frame is not None:
                frames.append(frame)
        return frames

    def read_all(self) -> bytes | None:
        """Read all buffered bytes, or ``None`` if empty.

        Useful for bulk operations where frame alignment isn't needed.
        """
        avail = self._inner.available
        if avail == 0:
            return None
        return self._inner.read(avail)

    def flush(self) -> bytes | None:
        """Return remaining bytes (possibly shorter than one frame).

        Returns ``None`` if the buffer is empty.  After this call the
        buffer is empty.
        """
        return self.read_all()

    # -- housekeeping --------------------------------------------------------

    def clear(self) -> None:
        """Discard all buffered data and reset write counter."""
        self._inner.clear()
        self._total_samples_written = 0


# ---------------------------------------------------------------------------
# AudioMixer — background noise generation and signal mixing
# ---------------------------------------------------------------------------

# Clipping bounds for int16 mixing.
_I16_MIN = np.int32(-32768)
_I16_MAX = np.int32(32767)


class AudioMixer:
    """Background noise generator with looped playback and signal mixing."""

    __slots__ = ("_buffer", "_offset", "_amplitude", "_sample_rate", "_enabled")

    def __init__(
        self,
        sample_rate: int,
        *,
        amplitude: int = 50,
        duration_s: float = 1.0,
        seed: int = 42,
        enabled: bool = True,
    ) -> None:
        """Args:
        sample_rate: Audio sample rate in Hz.
        amplitude: Peak amplitude of the noise in int16 range (0–32768).
            Default 50 is intentionally very quiet — a subtle hum.
        duration_s: Length of the internal noise loop in seconds.
            Longer loops sound more natural but use more memory
            (16 kHz × 1 s = 32 KB).
        seed: RNG seed for reproducible noise generation.
        enabled: If ``False``, all output methods return silence.

        """
        self._sample_rate = sample_rate
        self._amplitude = amplitude
        self._enabled = enabled
        self._offset: int = 0

        if amplitude > 0:
            self._buffer = generate_brown_noise(
                duration_s, sample_rate, amplitude=amplitude, seed=seed
            )
        else:
            self._buffer = np.zeros(int(duration_s * sample_rate), dtype=np.int16)

    # -- properties ----------------------------------------------------------

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def amplitude(self) -> int:
        return self._amplitude

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    # -- noise frame extraction ----------------------------------------------

    def next_frame(self, n_samples: int) -> np.ndarray:
        """Return the next *n_samples* from the looped noise buffer.

        If the mixer is disabled or amplitude is 0, returns a zero-filled
        array (silence).  The returned array is always a **copy** — safe
        to mutate.

        Args:
            n_samples: Number of int16 samples to return.

        Returns:
            ``np.ndarray`` of dtype ``int16`` with shape ``(n_samples,)``.

        """
        if not self._enabled or self._amplitude == 0:
            return np.zeros(n_samples, dtype=np.int16)

        total = len(self._buffer)
        start = self._offset % total
        end = start + n_samples

        if end <= total:
            frame = self._buffer[start:end].copy()
        else:
            # Wrap around the loop boundary
            frame = np.concatenate([self._buffer[start:], self._buffer[: end - total]])

        self._offset = end % total
        return frame

    def next_frame_bytes(self, n_samples: int) -> bytes:
        """Like :meth:`next_frame` but returns raw PCM16 bytes."""
        return self.next_frame(n_samples).tobytes()

    # -- mixing --------------------------------------------------------------

    @staticmethod
    def mix(signal: np.ndarray, noise: np.ndarray) -> np.ndarray:
        """Additively mix *signal* and *noise* with int16 clipping.

        Both inputs must be ``int16`` arrays of the same length.  Mixing
        is done in ``int32`` to prevent overflow, then clipped back to
        the ``int16`` range.

        Returns a new array — inputs are not modified.
        """
        mixed = signal.astype(np.int32) + noise.astype(np.int32)
        np.clip(mixed, _I16_MIN, _I16_MAX, out=mixed)
        return mixed.astype(np.int16)

    def mix_background(self, signal: np.ndarray) -> np.ndarray:
        """Mix the internal noise loop into *signal*.

        Convenience method: extracts ``len(signal)`` samples from the
        noise loop and mixes them into *signal*.  If the mixer is
        disabled, returns a copy of *signal* unchanged.
        """
        if not self._enabled or self._amplitude == 0:
            return signal.copy()
        noise = self.next_frame(len(signal))
        return self.mix(signal, noise)

    # -- state management ----------------------------------------------------

    def reset(self) -> None:
        """Reset the noise loop offset to the beginning."""
        self._offset = 0
