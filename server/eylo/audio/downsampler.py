"""PCM audio downsampling helpers."""

import logging
from typing import Union

import numba
import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


class AudioDownsampler:
    """Fast audio downsampler optimized for real-time processing."""

    def __init__(
        self,
        source_sample_rate: int = 48000,
        target_sample_rate: int = 8000,
        source_channels: int = 2,
        target_channels: int = 1,
        method: str = "fast",
    ):
        """Initialize audio downsampler.

        Args:
            source_sample_rate: Input sample rate (e.g., 48000)
            target_sample_rate: Output sample rate (e.g., 8000)
            source_channels: Input channels (1=mono, 2=stereo)
            target_channels: Output channels (1=mono, 2=stereo)
            method: "fast" (simple decimation), "iir" (scipy IIR), "buffered" (for small chunks)

        """
        self.source_sr = source_sample_rate
        self.target_sr = target_sample_rate
        self.source_channels = source_channels
        self.target_channels = target_channels
        self.method = method

        # Calculate decimation factor
        if source_sample_rate % target_sample_rate == 0:
            self.decimation_factor = source_sample_rate // target_sample_rate
            self.is_integer_decimation = True
        else:
            self.decimation_factor = source_sample_rate / target_sample_rate
            self.is_integer_decimation = False

        # Buffer for handling small chunks (used with "buffered" method)
        self.buffer = np.array([], dtype=np.int16)
        self.min_buffer_size = max(100, int(source_sample_rate * 0.1))  # 100ms buffer

        # NEW: Byte-level buffer for handling incomplete int16 samples
        self.byte_buffer = b""

        logger.info(
            f"AudioDownsampler initialized: {source_sample_rate}Hz -> {target_sample_rate}Hz, "
            f"{source_channels}ch -> {target_channels}ch, method={method}"
        )

    def process(self, audio_data: Union[np.ndarray, bytes]) -> np.ndarray:
        """Process audio data with downsampling and channel conversion.

        Args:
            audio_data: Input audio as numpy array or bytes

        Returns:
            Downsampled audio as numpy array

        """
        # Convert input to numpy array with byte buffering
        if isinstance(audio_data, bytes):
            # Add to byte buffer
            self.byte_buffer += audio_data

            # Only process complete int16 samples (2 bytes each)
            samples_available = len(self.byte_buffer) // 2
            if samples_available == 0:
                # Not enough data for even one sample
                logger.debug(
                    f"Insufficient data: {len(self.byte_buffer)} bytes, need at least 2"
                )
                return np.array([], dtype=np.int16)

            # Extract complete samples
            bytes_to_process = samples_available * 2
            try:
                audio_np = np.frombuffer(
                    self.byte_buffer[:bytes_to_process], dtype=np.int16
                )
            except ValueError as error:
                logger.error(
                    "Audio buffer conversion failed error_type=%s",
                    type(error).__name__,
                )
                # Clear corrupted buffer and return empty array
                self.byte_buffer = b""
                return np.array([], dtype=np.int16)

            # Keep remaining bytes for next call
            self.byte_buffer = self.byte_buffer[bytes_to_process:]

            logger.debug(
                f"Processed {bytes_to_process} bytes, {len(self.byte_buffer)} bytes remaining"
            )
        else:
            audio_np = np.asarray(audio_data, dtype=np.int16)

        # Flatten if needed (handle shapes like (1, 1920))
        if audio_np.ndim > 1:
            audio_np = audio_np.flatten()

        # Return empty array if no samples
        if len(audio_np) == 0:
            return np.array([], dtype=np.int16)

        # Choose processing method
        if self.method == "fast" and self.is_integer_decimation:
            return self._process_fast(audio_np)
        elif self.method == "iir":
            return self._process_iir(audio_np)
        elif self.method == "buffered":
            return self._process_buffered(audio_np)
        else:
            # Fallback to fast method
            return self._process_fast(audio_np)

    def clear_buffers(self):
        """Clear all internal buffers. Useful for resetting state between sessions."""
        self.buffer = np.array([], dtype=np.int16)
        self.byte_buffer = b""
        logger.debug("Cleared all audio buffers")

    def get_buffer_status(self) -> dict:
        """Get current buffer status for debugging."""
        return {
            "byte_buffer_size": len(self.byte_buffer),
            "sample_buffer_size": len(self.buffer),
            "bytes_needed_for_sample": 2 - (len(self.byte_buffer) % 2)
            if len(self.byte_buffer) % 2 != 0
            else 0,
        }

    def _process_fast(self, audio_np: np.ndarray) -> np.ndarray:
        """Fast processing using JIT-compiled functions."""
        if self.source_channels == 2 and self.target_channels == 1:
            # Stereo to mono + resampling
            if self.is_integer_decimation:
                return self._stereo_to_mono_decimate_jit(
                    audio_np, int(self.decimation_factor)
                )
            else:
                # Calculate target length for non-integer ratios
                input_samples = len(audio_np) // 2
                target_length = int(input_samples * self.target_sr / self.source_sr)
                return self._stereo_to_mono_resample_jit(audio_np, target_length)

        elif self.source_channels == 1 and self.target_channels == 1:
            # Mono to mono resampling
            if self.is_integer_decimation:
                return self._mono_decimate_jit(audio_np, int(self.decimation_factor))
            else:
                target_length = int(len(audio_np) * self.target_sr / self.source_sr)
                return self._mono_resample_jit(audio_np, target_length)
        else:
            raise NotImplementedError(
                f"Channel conversion {self.source_channels}->{self.target_channels} not implemented"
            )

    def _process_iir(self, audio_np: np.ndarray) -> np.ndarray:
        """Process using scipy IIR filtering (higher quality, slower)."""
        try:
            # Convert to mono if needed
            if self.source_channels == 2:
                mono = self._convert_stereo_to_mono(audio_np)
            else:
                mono = audio_np

            # Apply IIR decimation
            if self.is_integer_decimation:
                downsampled = signal.decimate(
                    mono, int(self.decimation_factor), ftype="iir"
                )
            else:
                # Use resampling for non-integer ratios
                from scipy.signal import resample

                target_length = int(len(mono) * self.target_sr / self.source_sr)
                downsampled = resample(mono, target_length)

            return downsampled.astype(np.int16)

        except ValueError as error:
            logger.warning(
                "IIR processing failed error_type=%s; using fast method",
                type(error).__name__,
            )
            return self._process_fast(audio_np)

    def _process_buffered(self, audio_np: np.ndarray) -> np.ndarray:
        """Buffer small chunks for more stable processing."""
        # Add to buffer
        self.buffer = np.concatenate([self.buffer, audio_np])

        # Process if buffer is large enough
        if len(self.buffer) >= self.min_buffer_size:
            # Process the buffer
            processed = self._process_iir(self.buffer)

            # For buffered mode, we process everything and clear the buffer
            # This is simpler and more appropriate for real-time streaming
            self.buffer = np.array([], dtype=np.int16)

            return processed

        # Return empty array if not enough data
        return np.array([], dtype=np.int16)

    def _convert_stereo_to_mono(self, stereo_audio: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono by averaging channels."""
        stereo_pairs = stereo_audio.reshape(-1, 2)
        return np.mean(stereo_pairs, axis=1).astype(np.int16)

    @staticmethod
    @numba.jit(nopython=True, cache=True, fastmath=True)
    def _stereo_to_mono_decimate_jit(
        audio_data: np.ndarray, decimation_factor: int
    ) -> np.ndarray:
        """JIT-compiled stereo to mono with integer decimation."""
        input_samples = len(audio_data) // 2  # Number of stereo pairs
        output_samples = input_samples // decimation_factor
        output = np.empty(output_samples, dtype=np.int16)

        for i in range(output_samples):
            # Get every Nth stereo pair
            base_idx = i * decimation_factor * 2
            left = np.int32(audio_data[base_idx])
            right = np.int32(audio_data[base_idx + 1])
            output[i] = np.int16((left + right) // 2)

        return output

    @staticmethod
    @numba.jit(nopython=True, cache=True, fastmath=True)
    def _stereo_to_mono_resample_jit(
        audio_data: np.ndarray, target_length: int
    ) -> np.ndarray:
        """JIT-compiled stereo to mono with resampling for non-integer ratios."""
        input_samples = len(audio_data) // 2  # Number of stereo pairs
        output = np.empty(target_length, dtype=np.int16)

        for i in range(target_length):
            # Linear interpolation between samples
            src_pos = i * (input_samples - 1) / (target_length - 1)
            src_idx = int(src_pos)
            frac = src_pos - src_idx

            # Get current stereo pair
            base_idx = src_idx * 2
            left1 = np.int32(audio_data[base_idx])
            right1 = np.int32(audio_data[base_idx + 1])
            mono1 = (left1 + right1) // 2

            if src_idx + 1 < input_samples and frac > 0:
                # Interpolate with next sample
                next_base_idx = (src_idx + 1) * 2
                left2 = np.int32(audio_data[next_base_idx])
                right2 = np.int32(audio_data[next_base_idx + 1])
                mono2 = (left2 + right2) // 2

                # Linear interpolation
                interpolated = mono1 + int(frac * (mono2 - mono1))
                output[i] = np.int16(interpolated)
            else:
                output[i] = np.int16(mono1)

        return output

    @staticmethod
    @numba.jit(nopython=True, cache=True, fastmath=True)
    def _mono_decimate_jit(
        audio_data: np.ndarray, decimation_factor: int
    ) -> np.ndarray:
        """JIT-compiled mono decimation for integer factors."""
        output_samples = len(audio_data) // decimation_factor
        output = np.empty(output_samples, dtype=np.int16)

        for i in range(output_samples):
            output[i] = audio_data[i * decimation_factor]

        return output

    @staticmethod
    @numba.jit(nopython=True, cache=True, fastmath=True)
    def _mono_resample_jit(audio_data: np.ndarray, target_length: int) -> np.ndarray:
        """JIT-compiled mono resampling for non-integer ratios."""
        input_length = len(audio_data)
        output = np.empty(target_length, dtype=np.int16)

        for i in range(target_length):
            # Linear interpolation
            src_pos = i * (input_length - 1) / (target_length - 1)
            src_idx = int(src_pos)
            frac = src_pos - src_idx

            if src_idx + 1 < input_length and frac > 0:
                # Interpolate between samples
                sample1 = np.int32(audio_data[src_idx])
                sample2 = np.int32(audio_data[src_idx + 1])
                interpolated = sample1 + int(frac * (sample2 - sample1))
                output[i] = np.int16(interpolated)
            else:
                output[i] = audio_data[src_idx]

        return output
