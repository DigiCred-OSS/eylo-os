"""Audio processing utilities.

Extracted from LiveKit Agents for vendor-independent audio manipulation.

Functions:
- combine_audio_frames: Combine multiple AudioFrames (LiveKit-compatible API)
- combine_frames: Merge frames and return raw bytes
"""

from .buffer import AudioFrame


def combine_audio_frames(frames: list[AudioFrame] | AudioFrame) -> AudioFrame:
    """Combine one or more AudioFrame objects into a single AudioFrame.

    This is the LiveKit-compatible API. Concatenates audio data from multiple
    frames, ensuring all frames have the same sample rate and number of channels.

    Args:
        frames: A single AudioFrame or list of AudioFrame objects to combine

    Returns:
        AudioFrame: A new AudioFrame containing the combined audio data

    Raises:
        ValueError: If frames list is empty
        ValueError: If frames have differing sample rates
        ValueError: If frames have differing numbers of channels

    Example:
        >>> frame1 = AudioFrame(data=b"\\x00\\x00", sample_rate=16000, num_channels=1, samples_per_channel=1)
        >>> frame2 = AudioFrame(data=b"\\x01\\x00", sample_rate=16000, num_channels=1, samples_per_channel=1)
        >>> combined = combine_audio_frames([frame1, frame2])
        >>> combined.samples_per_channel
        2

    """
    # Handle single frame
    if isinstance(frames, AudioFrame):
        return frames

    # Validate non-empty
    if not frames:
        raise ValueError("Cannot combine empty frame list")

    # Get reference values from first frame
    first_frame = frames[0]
    sample_rate = first_frame.sample_rate
    num_channels = first_frame.num_channels

    # Validate all frames have same properties
    for i, frame in enumerate(frames[1:], start=1):
        if frame.sample_rate != sample_rate:
            raise ValueError(
                f"All frames must have same sample_rate. "
                f"Frame 0 has {sample_rate}Hz, frame {i} has {frame.sample_rate}Hz"
            )
        if frame.num_channels != num_channels:
            raise ValueError(
                f"All frames must have same num_channels. "
                f"Frame 0 has {num_channels} channels, frame {i} has {frame.num_channels} channels"
            )

    # Concatenate audio data
    combined_data = b"".join(f.data for f in frames)

    # Calculate total samples
    total_samples = sum(f.samples_per_channel for f in frames)

    # Merge userdata dictionaries (later frames override earlier ones)
    combined_userdata = {}
    for frame in frames:
        if hasattr(frame, "userdata") and frame.userdata:
            combined_userdata.update(frame.userdata)

    return AudioFrame(
        data=combined_data,
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=total_samples,
        userdata=combined_userdata if combined_userdata else {},
    )


def combine_frames(frames: list[AudioFrame]) -> bytes:
    """Combine multiple frames and return raw audio bytes.

    Convenience function for getting raw PCM data from multiple frames.

    Args:
        frames: List of AudioFrame objects

    Returns:
        Combined raw audio bytes

    """
    return b"".join(f.data for f in frames)
