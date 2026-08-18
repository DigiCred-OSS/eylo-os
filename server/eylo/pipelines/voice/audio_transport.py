"""Streaming conversion between explicit voice media contracts."""

from __future__ import annotations

import audioop

from eylo.audio.ops import AudioMixer, StreamingResampler
from eylo.sockets.tts.schemas import TTSAudioFormat


class StreamingAudioTranscoder:
    """Convert one mono raw-audio stream without losing resampler state."""

    def __init__(
        self,
        *,
        source: TTSAudioFormat,
        target: TTSAudioFormat,
    ) -> None:
        self.source = source
        self.target = target
        self._resampler = (
            StreamingResampler(source.sample_rate, target.sample_rate)
            if source.sample_rate != target.sample_rate
            else None
        )

    def process(self, audio: bytes) -> bytes:
        """Convert one ordered chunk from provider media to transport media."""
        if not audio:
            return audio
        if self.source == self.target:
            return audio

        pcm = _decode_pcm16(audio, self.source.encoding)
        if self._resampler is not None:
            pcm = self._resampler.process(pcm)
        return _encode_pcm16(pcm, self.target.encoding)

    def reset(self) -> None:
        """Drop filter history when an interrupted utterance is discarded."""
        if self._resampler is not None:
            self._resampler.reset()


class ComfortAudioStream:
    """Generate quiet transport-ready audio while the Agent is thinking."""

    def __init__(
        self,
        *,
        target: TTSAudioFormat,
        amplitude: int,
        enabled: bool,
        frame_duration_ms: int = 20,
    ) -> None:
        self.target = target
        self._samples_per_frame = int(
            target.sample_rate * frame_duration_ms / 1000
        )
        self._mixer = AudioMixer(
            target.sample_rate,
            amplitude=amplitude,
            enabled=enabled,
        )
        self._encoder = StreamingAudioTranscoder(
            source=TTSAudioFormat(
                container="raw",
                encoding="pcm_s16le",
                sample_rate=target.sample_rate,
            ),
            target=target,
        )

    def next_frame(self) -> bytes:
        pcm = self._mixer.next_frame_bytes(self._samples_per_frame)
        return self._encoder.process(pcm)


def _decode_pcm16(audio: bytes, encoding: str) -> bytes:
    if encoding == "pcm_s16le":
        if len(audio) % 2:
            raise ValueError("PCM S16LE audio must contain complete samples.")
        return audio
    if encoding == "pcm_mulaw":
        return audioop.ulaw2lin(audio, 2)
    if encoding == "pcm_alaw":
        return audioop.alaw2lin(audio, 2)
    raise ValueError(f"Unsupported source audio encoding: {encoding}")


def _encode_pcm16(audio: bytes, encoding: str) -> bytes:
    if encoding == "pcm_s16le":
        return audio
    if encoding == "pcm_mulaw":
        return audioop.lin2ulaw(audio, 2)
    if encoding == "pcm_alaw":
        return audioop.lin2alaw(audio, 2)
    raise ValueError(f"Unsupported target audio encoding: {encoding}")
