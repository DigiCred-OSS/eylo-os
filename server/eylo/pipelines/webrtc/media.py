"""WebRTC media tracks for browser voice pipelines.

The socket layer owns SDP, ICE, and peer connection setup. These tracks own
runtime media policy: browser audio downsampling, STT/realtime forwarding,
recording taps, TTS playback draining, interruption buffer clearing, and
ambient thinking audio.
"""

from __future__ import annotations

import asyncio
import fractions
import logging
from typing import Optional

import arrow
import numpy as np
from aiortc import AudioStreamTrack, MediaStreamTrack
from av import AudioFrame

from eylo.audio.downsampler import AudioDownsampler
from eylo.audio.ops import (
    SILENCE_FRAME_16K_20MS,
    AudioChunkBuffer,
    generate_brown_noise,
)
from eylo.pipelines.websocket.schemas import WSSessionState

logger = logging.getLogger(__name__)

WEBRTC_STT_SAMPLE_RATE = 16000
WEBRTC_PCM_ENCODING = "pcm_s16le"


class IncomingAudioTrack(MediaStreamTrack):
    """Receives audio from browser and processes it through STT."""

    kind = "audio"

    def __init__(self, track: MediaStreamTrack, session_state: WSSessionState):
        super().__init__()
        self.track = track
        self.session_state = session_state
        self._started = False

        self.source_sample_rate = 48000
        self.target_sample_rate = WEBRTC_STT_SAMPLE_RATE
        self.source_channels = 2
        self.target_channels = 1
        self.downsampler: Optional[AudioDownsampler] = None

        self.audio_buffer = bytearray()
        self._buffer_has_signal = False
        self.buffer_duration_ms = 50
        self.samples_accumulated = 0

        self._last_stt_send_time = None
        self._stt_send_interval = self.buffer_duration_ms / 1000.0

    async def recv(self):
        """Receive browser frames, downsample them, and forward STT-ready chunks."""
        frame = await self.track.recv()

        if not self._started:
            self._started = True
            self.source_sample_rate = frame.sample_rate
            self.source_channels = len(frame.layout.channels)

            self.downsampler = AudioDownsampler(
                source_sample_rate=self.source_sample_rate,
                target_sample_rate=self.target_sample_rate,
                source_channels=self.source_channels,
                target_channels=self.target_channels,
                method="fast",
            )

            logger.info("IncomingAudioTrack.recv started receiving frames")
            logger.info("=== Incoming Audio Format ===")
            logger.info("Format: %s (%s bits)", frame.format.name, frame.format.bits)
            logger.info(
                "Layout: %s (channels: %s)",
                frame.layout.name,
                frame.layout.channels,
            )
            logger.info("Sample Rate: %s Hz", frame.sample_rate)
            logger.info("Samples: %s", frame.samples)
            logger.info("=== Target Audio Format ===")
            logger.info("Sample Rate: %s Hz", self.target_sample_rate)
            logger.info("Channels: %s", self.target_channels)
            self._configure_user_recording_format()

        try:
            downsampled_audio = self.downsampler.process(frame.to_ndarray())

            if len(downsampled_audio) == 0:
                return frame

            audio_bytes = downsampled_audio.tobytes()
            self._record_user_audio(audio_bytes)
            self.audio_buffer.extend(audio_bytes)
            self._buffer_has_signal = self._buffer_has_signal or bool(
                np.any(downsampled_audio != 0)
            )
            self.samples_accumulated += len(downsampled_audio)

            target_samples = int(
                self.target_sample_rate * self.buffer_duration_ms / 1000
            )
            if self.samples_accumulated >= target_samples:
                current_time = asyncio.get_event_loop().time()

                if self._last_stt_send_time is not None:
                    elapsed = current_time - self._last_stt_send_time
                    time_to_wait = self._stt_send_interval - elapsed
                    if time_to_wait > 0:
                        await asyncio.sleep(time_to_wait)

                self._last_stt_send_time = asyncio.get_event_loop().time()
                await self._send_audio_to_stt()

        except Exception as error:
            logger.error(
                "Audio processing for STT failed error_type=%s",
                type(error).__name__,
            )

        return frame

    async def _send_audio_to_stt(self):
        """Send accumulated audio buffer to STT or realtime vendor."""
        if len(self.audio_buffer) > 0:
            audio_chunk = bytes(self.audio_buffer)
            buffer_has_signal = self._buffer_has_signal

            if self.session_state.realtime_mode and self.session_state.realtime_manager:
                try:
                    await self.session_state.realtime_manager.send_audio(audio_chunk)
                    self._mark_transport_activity(buffer_has_signal)
                except Exception as error:
                    logger.error(
                        "Sending audio to realtime manager failed error_type=%s",
                        type(error).__name__,
                    )
                self.audio_buffer.clear()
                self._buffer_has_signal = False
                self.samples_accumulated = 0
                return

            request_queue = getattr(self.session_state, "stt_request_queue", None)
            if request_queue is not None:
                try:
                    request_queue.put_nowait(audio_chunk)
                except asyncio.QueueFull:
                    logger.warning(
                        "IncomingAudioTrack: STT request queue full, dropping oldest chunk"
                    )
                    try:
                        dropped = request_queue.get_nowait()
                        try:
                            request_queue.task_done()
                        except ValueError:
                            logger.debug(
                                "IncomingAudioTrack: task_done called without matching get"
                            )
                        logger.debug(
                            "IncomingAudioTrack: Dropped %s bytes from STT queue",
                            len(dropped)
                            if isinstance(dropped, (bytes, bytearray))
                            else "unknown",
                        )
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        request_queue.put_nowait(audio_chunk)
                    except asyncio.QueueFull:
                        logger.error(
                            "IncomingAudioTrack: Unable to enqueue audio after drop; chunk discarded"
                        )
                    else:
                        self._mark_transport_activity(buffer_has_signal)
                else:
                    self._mark_transport_activity(buffer_has_signal)
            elif self.session_state.stt_started and self.session_state.stt_socket:
                try:
                    await self.session_state.stt_socket.send_audio(audio_chunk)
                    self._mark_transport_activity(buffer_has_signal)
                except Exception as error:
                    logger.error(
                        "Sending audio to STT failed error_type=%s",
                        type(error).__name__,
                    )
            else:
                logger.warning("STT not ready, dropping audio packet from agent_peer.")
                self.audio_buffer.clear()
                self._buffer_has_signal = False
                self.samples_accumulated = 0

        self.audio_buffer.clear()
        self._buffer_has_signal = False
        self.samples_accumulated = 0

    def _mark_transport_activity(self, buffer_has_signal: bool) -> None:
        """Keep carrier silence separate from observable caller activity."""
        if buffer_has_signal:
            self.session_state.last_activity_at = arrow.utcnow().timestamp()

    def _record_user_audio(self, audio_bytes: bytes) -> None:
        audio_recorder = getattr(self.session_state, "audio_recorder", None)
        if audio_recorder:
            audio_recorder.record_user(audio_bytes)

    def _configure_user_recording_format(self) -> None:
        audio_recorder = getattr(self.session_state, "audio_recorder", None)
        if audio_recorder:
            audio_recorder.set_user_audio_format(
                sample_rate=self.target_sample_rate,
                encoding=WEBRTC_PCM_ENCODING,
            )

    def stop(self):
        super().stop()
        if hasattr(self, "track"):
            self.track.stop()


class OutgoingAudioTrack(AudioStreamTrack):
    """Sends TTS/realtime audio to the browser as 16kHz mono frames."""

    kind = "audio"

    _DEFAULT_AMBIENT_AMPLITUDE = 50
    _MIN_AMBIENT_AMPLITUDE = 0
    _MAX_AMBIENT_AMPLITUDE = 500

    def __init__(self, session_state):
        super().__init__()
        self.session_state = session_state

        self.sample_rate = 16000
        self.channels = 1
        self.frame_duration_ms = 20
        self.samples_per_frame = int(self.sample_rate * self.frame_duration_ms / 1000)

        self.audio_buffer = AudioChunkBuffer()
        self.buffer_lock = asyncio.Lock()

        self._pts = 0
        self._time_base = fractions.Fraction(1, self.sample_rate)
        self._started = False
        self._frame_count = 0
        self._last_frame_time = None
        self._frame_interval = self.frame_duration_ms / 1000.0

        ambient_cfg = getattr(session_state, "ambient_noise_config", None) or {}
        self._ambient_enabled = bool(ambient_cfg.get("enabled", True))
        self._ambient_amplitude = self._coerce_ambient_amplitude(
            ambient_cfg.get("amplitude", self._DEFAULT_AMBIENT_AMPLITUDE)
        )

        self._ambient_noise = generate_brown_noise(
            duration_s=1.0,
            sample_rate=self.sample_rate,
            amplitude=self._ambient_amplitude,
        )
        self._ambient_offset = 0

        logger.info(
            "OutgoingAudioTrack initialized: %sHz, frame_size=%s samples (%sms), "
            "ambient_enabled=%s, ambient_amplitude=%s",
            self.sample_rate,
            self.samples_per_frame,
            self.frame_duration_ms,
            self._ambient_enabled,
            self._ambient_amplitude,
        )

    async def recv(self):
        """Generate audio frames from TTS output with proper rate limiting."""
        if self.session_state.tts_interrupt_event.is_set():
            self.session_state.transport_playback_gate.cancel()
            async with self.buffer_lock:
                if self.audio_buffer.available > 0:
                    logger.info(
                        "TTS interruption: Clearing %s bytes from OutgoingAudioTrack buffer.",
                        self.audio_buffer.available,
                    )
                    self.audio_buffer.clear()
            self.session_state.tts_interrupt_event.clear()
            logger.info("TTS interruption: Cleared tts_interrupt_event.")

        try:
            current_time = asyncio.get_event_loop().time()

            if self._last_frame_time is not None:
                elapsed = current_time - self._last_frame_time
                time_to_wait = self._frame_interval - elapsed
                if time_to_wait > 0:
                    await asyncio.sleep(time_to_wait)

            self._last_frame_time = asyncio.get_event_loop().time()

            await self._process_tts_queue()
            await self._complete_transport_playback_if_drained()
            frame_samples = await self._get_next_frame()
            frame = self._create_audio_frame(frame_samples)

            if not self._started and np.any(frame_samples != 0):
                self._started = True
                logger.info(
                    "Started sending 16kHz TTS audio to browser with rate limiting"
                )

            self._frame_count += 1
            return frame

        except Exception as error:
            logger.error(
                "Outgoing audio receive failed error_type=%s",
                type(error).__name__,
            )
            return self._create_silence_frame()

    async def _process_tts_queue(self):
        """Process TTS audio from queue with minimal overhead."""
        if (
            not hasattr(self.session_state, "tts_response_queue")
            or self.session_state.tts_response_queue is None
        ):
            return

        while not self.session_state.tts_response_queue.empty():
            try:
                tts_response = self.session_state.tts_response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            except Exception as error:
                logger.error(
                    "Processing TTS response failed error_type=%s",
                    type(error).__name__,
                )
                continue

            if isinstance(tts_response, bytes) and len(tts_response) > 0:
                async with self.buffer_lock:
                    self.audio_buffer.write(tts_response)
                    buffer_size = self.audio_buffer.available
                logger.debug(
                    "[TTS_PIPELINE] tts_response_queue -> audio_buffer: %s bytes "
                    "(buffer_available=%s)",
                    len(tts_response),
                    buffer_size,
                )
            else:
                logger.debug(
                    "[TTS_PIPELINE] Skipped non-bytes TTS response: type=%s, len=%s",
                    type(tts_response),
                    len(tts_response) if tts_response else 0,
                )

            try:
                self.session_state.tts_response_queue.task_done()
            except ValueError:
                logger.debug(
                    "OutgoingAudioTrack: task_done called without matching get"
                )

    async def _complete_transport_playback_if_drained(self) -> None:
        """Publish audible completion after the final PCM frame was consumed."""
        response_queue = getattr(self.session_state, "tts_response_queue", None)
        if response_queue is not None and not response_queue.empty():
            return
        async with self.buffer_lock:
            if self.audio_buffer.available > 0:
                return
        if not self.session_state.transport_playback_gate.complete_if_drained():
            return
        callback = self.session_state.voice_output_drained_callback
        if callback is not None:
            callback()

    async def _get_next_frame(self) -> np.ndarray:
        """Extract next frame of int16 samples with minimal processing."""
        async with self.buffer_lock:
            bytes_needed = self.samples_per_frame * 2
            avail = self.audio_buffer.available

            if avail >= bytes_needed:
                frame_bytes = self.audio_buffer.read(bytes_needed)
                return np.frombuffer(frame_bytes, dtype=np.int16)

            if avail >= 2:
                available_even = (avail // 2) * 2
                frame_bytes = self.audio_buffer.read(available_even)
                partial_samples = np.frombuffer(frame_bytes, dtype=np.int16)

                frame_samples = SILENCE_FRAME_16K_20MS.copy()
                frame_samples[: len(partial_samples)] = partial_samples
                return frame_samples

            if (
                self._ambient_enabled
                and self._ambient_amplitude > 0
                and getattr(self.session_state, "is_agent_thinking", False)
            ):
                return self._next_ambient_frame()
            return SILENCE_FRAME_16K_20MS.copy()

    @classmethod
    def _coerce_ambient_amplitude(cls, amplitude: object) -> int:
        try:
            normalized = int(amplitude)
        except (TypeError, ValueError):
            normalized = cls._DEFAULT_AMBIENT_AMPLITUDE
        return max(
            cls._MIN_AMBIENT_AMPLITUDE,
            min(cls._MAX_AMBIENT_AMPLITUDE, normalized),
        )

    def _next_ambient_frame(self) -> np.ndarray:
        n = self.samples_per_frame
        total = len(self._ambient_noise)
        start = self._ambient_offset % total
        end = start + n

        if end <= total:
            frame = self._ambient_noise[start:end].copy()
        else:
            frame = np.concatenate(
                [
                    self._ambient_noise[start:],
                    self._ambient_noise[: end - total],
                ]
            )

        self._ambient_offset = end % total
        return frame

    def _create_audio_frame(self, samples: np.ndarray) -> AudioFrame:
        try:
            if len(samples) != self.samples_per_frame:
                logger.warning(
                    "Frame size mismatch: %s != %s",
                    len(samples),
                    self.samples_per_frame,
                )

                if len(samples) > self.samples_per_frame:
                    samples = samples[: self.samples_per_frame]
                else:
                    padded = np.zeros(self.samples_per_frame, dtype=np.int16)
                    padded[: len(samples)] = samples
                    samples = padded

            audio_data = samples.reshape(1, -1)
            frame = AudioFrame.from_ndarray(audio_data, format="s16", layout="mono")
            frame.pts = self._pts
            frame.sample_rate = self.sample_rate
            frame.time_base = self._time_base

            self._pts += self.samples_per_frame
            return frame

        except Exception as error:
            logger.error(
                "Creating audio frame failed error_type=%s",
                type(error).__name__,
            )
            return self._create_silence_frame()

    def _create_silence_frame(self) -> AudioFrame:
        silence_data = SILENCE_FRAME_16K_20MS.reshape(1, -1)

        frame = AudioFrame.from_ndarray(silence_data, format="s16", layout="mono")
        frame.pts = self._pts
        frame.sample_rate = self.sample_rate
        frame.time_base = self._time_base

        self._pts += self.samples_per_frame
        return frame

    async def add_tts_audio(self, audio_data: bytes):
        if not audio_data or len(audio_data) == 0:
            return

        async with self.buffer_lock:
            self.audio_buffer.write(audio_data)

    def get_buffer_stats(self) -> dict:
        avail = self.audio_buffer.available
        return {
            "buffer_bytes": avail,
            "buffer_samples": avail // 2,
            "buffer_seconds": (avail // 2) / self.sample_rate,
            "frames_sent": self._frame_count,
            "started": self._started,
            "sample_rate": self.sample_rate,
        }

    async def clear_buffers(self):
        self.session_state.transport_playback_gate.cancel()
        async with self.buffer_lock:
            self.audio_buffer.clear()
            logger.debug("Cleared audio buffers")

    def stop(self):
        self.session_state.transport_playback_gate.cancel()
        super().stop()
