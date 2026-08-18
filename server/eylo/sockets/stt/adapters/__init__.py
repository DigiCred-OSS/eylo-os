"""Provider implementations for the canonical STT socket contract."""

from .assemblyai_adapter import AssemblyAIAdapter
from .cartesia_adapter import CartesiaAdapter
from .deepgram_adapter import DeepgramAdapter
from .deepgram_flux_adapter import DeepgramFluxConfig, DeepgramFluxSTT
from .gladia_adapter import GladiaAdapter
from .google_adapter import GoogleAdapter
from .revai_adapter import RevAIAdapter
from .sarvam_adapter import SarvamSTT, SarvamSTTConfig
from .speechmatics_adapter import SpeechmaticsAdapter

__all__ = [
    "AssemblyAIAdapter",
    "CartesiaAdapter",
    "DeepgramAdapter",
    "DeepgramFluxConfig",
    "DeepgramFluxSTT",
    "GladiaAdapter",
    "GoogleAdapter",
    "RevAIAdapter",
    "SarvamSTT",
    "SarvamSTTConfig",
    "SpeechmaticsAdapter",
]
