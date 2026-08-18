"""Pure Python audio resampling using scipy.

Extracted patterns from LiveKit Agents AudioResampler, but implemented dependency-free
using scipy instead of Sox (C++ library).

Converts audio between different sample rates (e.g., 48kHz → 16kHz) for vendor compatibility.

This module provides:
- AudioResampler: Main resampling class with quality levels
- AudioResamplerQuality: Quality enum (FAST, MEDIUM, HIGH)
"""

from enum import Enum

import numpy as np
from scipy import signal

from .buffer import AudioFrame


class AudioResamplerQuality(str, Enum):
    """Resampling quality levels.

    Higher quality = better audio but slower processing.
    Lower quality = faster processing but may introduce artifacts.
    """

    FAST = "FAST"  # Linear interpolation (~1ms for 100ms audio)
    MEDIUM = "MEDIUM"  # Scipy resample (default, ~3ms for 100ms audio)
    HIGH = "HIGH"  # Scipy resample_poly (best quality, ~5ms for 100ms audio)


class AudioResampler:
    """Resample audio from one sample rate to another."""

    def __init__(
        self,
        input_rate: int,
        output_rate: int,
        *,
        num_channels: int = 1,
        quality: AudioResamplerQuality = AudioResamplerQuality.MEDIUM,
    ):
        """Initialize audio resampler.

        Args:
            input_rate: Input sample rate in Hz (e.g., 48000)
            output_rate: Output sample rate in Hz (e.g., 16000)
            num_channels: Number of audio channels (1=mono, 2=stereo)
            quality: Resampling quality level (FAST, MEDIUM, HIGH)

        Raises:
            ValueError: If sample rates are invalid or num_channels < 1

        """
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError(
                f"Sample rates must be positive, got input={input_rate}, output={output_rate}"
            )
        if num_channels < 1:
            raise ValueError(f"num_channels must be >= 1, got {num_channels}")

        self.input_rate = input_rate
        self.output_rate = output_rate
        self.num_channels = num_channels
        self.quality = quality

        # Calculate ratio
        self.ratio = output_rate / input_rate

        # Buffer for partial samples (streaming)
        self._buffer: np.ndarray | None = None

    def push(self, data: bytes | AudioFrame) -> list[AudioFrame]:
        """Push audio data and get resampled output.

        This method accepts audio data, resamples it, and returns any complete
        output frames. Some data may be buffered internally for streaming continuity.

        Args:
            data: Audio data as bytes (16-bit PCM) or AudioFrame

        Returns:
            List of resampled AudioFrame objects (may be empty if buffering)

        Raises:
            ValueError: If data format is invalid

        Example:
            >>> resampler = AudioResampler(48000, 16000)
            >>> frame = AudioFrame(data=audio_bytes, sample_rate=48000, num_channels=1, samples_per_channel=4800)
            >>> output = resampler.push(frame)
            >>> output[0].sample_rate
            16000

        """
        # Extract audio data
        if isinstance(data, AudioFrame):
            audio_bytes = data.data
            if data.sample_rate != self.input_rate:
                raise ValueError(
                    f"AudioFrame sample_rate ({data.sample_rate}) doesn't match resampler input_rate ({self.input_rate})"
                )
            if data.num_channels != self.num_channels:
                raise ValueError(
                    f"AudioFrame num_channels ({data.num_channels}) doesn't match resampler num_channels ({self.num_channels})"
                )
        else:
            audio_bytes = data

        # Convert to int16 samples
        samples = np.frombuffer(audio_bytes, dtype=np.int16)

        # Add buffered data from previous push
        if self._buffer is not None:
            samples = np.concatenate([self._buffer, samples])
            self._buffer = None

        # Handle multi-channel (interleaved format)
        if self.num_channels > 1:
            # Reshape to (samples, channels)
            samples = samples.reshape(-1, self.num_channels)

        # Resample
        resampled = self._resample_array(samples)

        # For streaming: buffer last few samples for smooth transitions
        # This prevents edge artifacts when concatenating frames
        buffer_size = 10  # samples to keep for next push
        if len(resampled) > buffer_size:
            self._buffer = resampled[-buffer_size:]
            resampled = resampled[:-buffer_size]
        else:
            # Not enough data to output yet
            self._buffer = resampled
            return []

        # Convert back to interleaved if multi-channel
        if self.num_channels > 1:
            resampled = resampled.flatten()

        # Convert to bytes
        resampled_bytes = resampled.astype(np.int16).tobytes()
        samples_per_channel = len(resampled) // self.num_channels

        return [
            AudioFrame(
                data=resampled_bytes,
                sample_rate=self.output_rate,
                num_channels=self.num_channels,
                samples_per_channel=samples_per_channel,
            )
        ]

    def flush(self) -> list[AudioFrame]:
        """Flush remaining buffered data.

        Call this when no more input data will be provided to get any
        buffered samples as a final output frame.

        Returns:
            List with final AudioFrame (or empty if no buffered data)

        Example:
            >>> final_frames = resampler.flush()
            >>> for frame in final_frames:
            ...     await process(frame)

        """
        if self._buffer is None or len(self._buffer) == 0:
            return []

        resampled = self._buffer
        self._buffer = None

        # Convert back to interleaved if multi-channel
        if self.num_channels > 1:
            resampled = resampled.flatten()

        resampled_bytes = resampled.astype(np.int16).tobytes()
        samples_per_channel = len(resampled) // self.num_channels

        return [
            AudioFrame(
                data=resampled_bytes,
                sample_rate=self.output_rate,
                num_channels=self.num_channels,
                samples_per_channel=samples_per_channel,
            )
        ]

    def _resample_array(self, samples: np.ndarray) -> np.ndarray:
        """Resample numpy array using configured quality.

        Args:
            samples: Input samples (1D for mono, 2D for multi-channel)

        Returns:
            Resampled samples in same format

        """
        if self.input_rate == self.output_rate:
            # No resampling needed
            return samples

        # Calculate target number of samples
        if samples.ndim == 1:
            # Mono
            num_input_samples = len(samples)
        else:
            # Multi-channel input stores samples by channel.
            num_input_samples = samples.shape[0]

        num_output_samples = int(num_input_samples * self.ratio)

        if num_output_samples == 0:
            return np.array([], dtype=np.int16)

        # Apply resampling based on quality
        if self.quality == AudioResamplerQuality.FAST:
            # Fast linear interpolation
            return self._resample_linear(samples, num_output_samples)
        elif self.quality == AudioResamplerQuality.MEDIUM:
            # Scipy resample (FFT-based, good quality)
            return self._resample_scipy(samples, num_output_samples)
        else:  # HIGH
            # Scipy resample_poly (polyphase filtering, best quality)
            return self._resample_poly(samples, num_output_samples)

    def _resample_linear(
        self, samples: np.ndarray, num_output_samples: int
    ) -> np.ndarray:
        """Fast linear interpolation resampling.

        Args:
            samples: Input samples
            num_output_samples: Target number of output samples

        Returns:
            Resampled samples

        """
        if samples.ndim == 1:
            # Mono
            input_indices = np.arange(len(samples))
            output_indices = np.linspace(0, len(samples) - 1, num_output_samples)
            return np.interp(output_indices, input_indices, samples).astype(np.int16)
        else:
            # Multi-channel: resample each channel independently
            resampled_channels = []
            for ch in range(samples.shape[1]):
                input_indices = np.arange(samples.shape[0])
                output_indices = np.linspace(
                    0, samples.shape[0] - 1, num_output_samples
                )
                resampled = np.interp(output_indices, input_indices, samples[:, ch])
                resampled_channels.append(resampled)
            return np.column_stack(resampled_channels).astype(np.int16)

    def _resample_scipy(
        self, samples: np.ndarray, num_output_samples: int
    ) -> np.ndarray:
        """Scipy FFT-based resampling (medium quality).

        Args:
            samples: Input samples
            num_output_samples: Target number of output samples

        Returns:
            Resampled samples

        """
        if samples.ndim == 1:
            # Mono
            resampled = signal.resample(samples, num_output_samples)
            return np.clip(resampled, -32768, 32767).astype(np.int16)
        else:
            # Multi-channel: resample each channel
            resampled_channels = []
            for ch in range(samples.shape[1]):
                resampled = signal.resample(samples[:, ch], num_output_samples)
                resampled_channels.append(resampled)
            resampled = np.column_stack(resampled_channels)
            return np.clip(resampled, -32768, 32767).astype(np.int16)

    def _resample_poly(
        self, samples: np.ndarray, num_output_samples: int
    ) -> np.ndarray:
        """Scipy polyphase filtering resampling (highest quality).

        Args:
            samples: Input samples
            num_output_samples: Target number of output samples

        Returns:
            Resampled samples

        """
        # resample_poly requires integer up/down factors
        # Find greatest common divisor for optimal performance
        from math import gcd

        g = gcd(self.input_rate, self.output_rate)
        up = self.output_rate // g
        down = self.input_rate // g

        if samples.ndim == 1:
            # Mono
            resampled = signal.resample_poly(samples, up, down)
            # Trim to exact length (resample_poly may overshoot)
            resampled = resampled[:num_output_samples]
            return np.clip(resampled, -32768, 32767).astype(np.int16)
        else:
            # Multi-channel: resample each channel
            resampled_channels = []
            for ch in range(samples.shape[1]):
                resampled = signal.resample_poly(samples[:, ch], up, down)
                resampled = resampled[:num_output_samples]
                resampled_channels.append(resampled)
            resampled = np.column_stack(resampled_channels)
            return np.clip(resampled, -32768, 32767).astype(np.int16)

    def __repr__(self) -> str:
        return (
            f"AudioResampler(input_rate={self.input_rate}, output_rate={self.output_rate}, "
            f"num_channels={self.num_channels}, quality={self.quality.value})"
        )
