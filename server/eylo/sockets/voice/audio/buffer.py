"""Audio buffering and streaming utilities.

Extracted from LiveKit Agents (livekit-agents/livekit/agents/utils/audio.py)
to provide vendor-independent audio processing.

These utilities handle:
- Buffering variable-size audio chunks
- Converting to fixed-size frames for WebSocket streaming
- Audio frame dataclass for consistent representation
"""

import io
import wave
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioFrame:
    """Represents a chunk of audio data.

    Attributes:
        data: Raw audio bytes (PCM 16-bit)
        sample_rate: Samples per second (e.g., 16000, 48000)
        num_channels: Number of audio channels (1=mono, 2=stereo)
        samples_per_channel: Number of samples in this frame per channel
        userdata: Optional dictionary for custom metadata

    """

    data: bytes
    sample_rate: int
    num_channels: int
    samples_per_channel: int
    userdata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Duration of this audio frame in seconds."""
        return self.samples_per_channel / self.sample_rate

    @property
    def size_bytes(self) -> int:
        """Total size in bytes."""
        return len(self.data)

    def to_wav_bytes(self) -> bytes:
        """Convert audio frame to WAV-formatted byte stream.

        Returns:
            bytes: Audio data encoded in WAV format with proper headers

        Example:
            >>> frame = AudioFrame(data=audio_bytes, sample_rate=16000, num_channels=1, samples_per_channel=1600)
            >>> wav_data = frame.to_wav_bytes()
            >>> with open("output.wav", "wb") as f:
            ...     f.write(wav_data)

        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(self.num_channels)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(self.data)
        return buffer.getvalue()

    @classmethod
    def from_wav_bytes(cls, wav_bytes: bytes) -> "AudioFrame":
        """Create AudioFrame from WAV-formatted bytes.

        Args:
            wav_bytes: WAV file data as bytes

        Returns:
            AudioFrame: Parsed audio frame

        Raises:
            ValueError: If WAV data is invalid or unsupported format

        Example:
            >>> with open("input.wav", "rb") as f:
            ...     wav_data = f.read()
            >>> frame = AudioFrame.from_wav_bytes(wav_data)

        """
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, "rb") as wav_file:
            # Validate format
            if wav_file.getsampwidth() != 2:
                raise ValueError(
                    f"Only 16-bit PCM is supported, got {wav_file.getsampwidth() * 8}-bit"
                )

            num_channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            samples_per_channel = len(audio_data) // (
                num_channels * 2
            )  # 2 bytes per sample

            return cls(
                data=audio_data,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
            )

    @classmethod
    def create(
        cls, sample_rate: int, num_channels: int, samples_per_channel: int
    ) -> "AudioFrame":
        """Create empty AudioFrame with zeroed data.

        Args:
            sample_rate: Sample rate in Hz
            num_channels: Number of channels (1=mono, 2=stereo)
            samples_per_channel: Number of samples per channel

        Returns:
            AudioFrame: New frame with zero-initialized data

        Example:
            >>> frame = AudioFrame.create(sample_rate=16000, num_channels=1, samples_per_channel=320)
            >>> len(frame.data)
            640

        """
        data_size = (
            samples_per_channel * num_channels * 2
        )  # 2 bytes per sample (16-bit)
        return cls(
            data=bytes(data_size),
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples_per_channel,
        )


class AudioBuffer:
    """Buffer for collecting audio frames.

    Useful for accumulating variable-sized audio chunks before processing.

    Example:
        buffer = AudioBuffer()
        buffer.append(frame1)
        buffer.append(frame2)
        total_duration = buffer.duration()  # Get total buffered time
        buffer.clear()  # Reset buffer

    """

    def __init__(self):
        self._frames: list[AudioFrame] = []

    def append(self, frame: AudioFrame) -> None:
        """Add frame to buffer."""
        self._frames.append(frame)

    def clear(self) -> None:
        """Clear all buffered frames."""
        self._frames.clear()

    def duration(self) -> float:
        """Total duration of buffered audio in seconds."""
        return sum(f.duration for f in self._frames)

    def frames(self) -> list[AudioFrame]:
        """Get all buffered frames (returns copy)."""
        return self._frames.copy()

    def __len__(self) -> int:
        """Number of frames in buffer."""
        return len(self._frames)


class AudioByteStream:
    """Convert variable-size audio bytes to fixed-size chunks."""

    def __init__(
        self,
        sample_rate: int,
        num_channels: int,
        samples_per_channel: int,
    ):
        """Initialize audio byte stream.

        Args:
            sample_rate: Sample rate in Hz (e.g., 16000, 48000)
            num_channels: Number of channels (1=mono, 2=stereo)
            samples_per_channel: Target samples per chunk

        """
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.samples_per_channel = samples_per_channel

        self._bytes_per_sample = 2  # 16-bit PCM audio
        self._chunk_size = samples_per_channel * num_channels * self._bytes_per_sample
        self._buffer = bytearray()

    def write(self, data: bytes) -> list[AudioFrame]:
        """Write audio bytes, returns completed chunks.

        Args:
            data: Raw audio bytes to buffer

        Returns:
            List of completed AudioFrame chunks (may be empty if not enough data)

        """
        self._buffer.extend(data)

        frames = []
        while len(self._buffer) >= self._chunk_size:
            chunk_data = bytes(self._buffer[: self._chunk_size])
            self._buffer = self._buffer[self._chunk_size :]

            frames.append(
                AudioFrame(
                    data=chunk_data,
                    sample_rate=self.sample_rate,
                    num_channels=self.num_channels,
                    samples_per_channel=self.samples_per_channel,
                )
            )

        return frames

    def flush(self) -> list[AudioFrame]:
        """Return remaining data as final frame.

        Returns:
            List with remaining audio as AudioFrame (or empty list if no data)

        """
        if not self._buffer:
            return []

        # Get remaining data
        remaining = bytes(self._buffer)
        self._buffer.clear()

        # Calculate actual samples
        bytes_per_sample = self._bytes_per_sample * self.num_channels
        actual_samples = len(remaining) // bytes_per_sample

        return [
            AudioFrame(
                data=remaining,
                sample_rate=self.sample_rate,
                num_channels=self.num_channels,
                samples_per_channel=actual_samples,
            )
        ]

    def pending_bytes(self) -> int:
        """Number of bytes currently buffered."""
        return len(self._buffer)
