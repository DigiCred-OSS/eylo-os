"""Public exports for the `voice` socket package."""

from .buffer import AudioBuffer, AudioByteStream, AudioFrame
from .resampler import AudioResampler, AudioResamplerQuality
from .utils import combine_audio_frames, combine_frames

__all__ = [
    # Core
    "AudioFrame",
    "AudioBuffer",
    "AudioByteStream",
    # Resampling (Phase 1)
    "AudioResampler",
    "AudioResamplerQuality",
    # Utilities
    "combine_audio_frames",  # LiveKit-compatible
    "combine_frames",  # Raw bytes
]
