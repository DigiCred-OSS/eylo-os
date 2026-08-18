"""Apply provider-independent voice behavior to a live session."""

from __future__ import annotations

from typing import Any, Protocol

from eylo.modules.voice.schemas.api import BackgroundAudioConfig, VoiceConfig


class VoiceInteractionState(Protocol):
    ambient_noise_config: dict[str, Any]
    filler_config: dict[str, Any]


def apply_voice_interaction_config(
    session_state: VoiceInteractionState,
    voice_config: VoiceConfig,
) -> None:
    """Apply the canonical background-audio section to a live session."""
    background_audio = resolve_background_audio_config(voice_config)
    session_state.ambient_noise_config = background_audio.ambient_noise.model_dump()
    session_state.filler_config = background_audio.filler.model_dump()


def resolve_background_audio_config(
    voice_config: VoiceConfig,
) -> BackgroundAudioConfig:
    """Return the canonical background-audio section."""
    return voice_config.background_audio


__all__ = ["apply_voice_interaction_config", "resolve_background_audio_config"]
