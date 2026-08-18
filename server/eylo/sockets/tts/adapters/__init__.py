"""Provider implementations for the canonical TTS socket contract.

Each adapter exposes `send_text`, `receive_audio`, `flush`, interruption, and
connection lifecycle through `TTSVendorAdapter`.
"""

from .deepgram_adapter import DeepgramTTSAdapter, DeepgramTTSConfig
from .groq_adapter import GroqTTSAdapter, GroqTTSConfig
from .hume_adapter import HumeTTSAdapter, HumeTTSConfig
from .murf_adapter import MurfTTSAdapter, MurfTTSConfig
from .openai_adapter import OpenAITTSAdapter, OpenAITTSConfig
from .rime_adapter import RimeTTSAdapter, RimeTTSConfig
from .smallest_adapter import SmallestTTSAdapter, SmallestTTSConfig

__all__ = [
    "DeepgramTTSAdapter",
    "DeepgramTTSConfig",
    "GroqTTSAdapter",
    "GroqTTSConfig",
    "HumeTTSAdapter",
    "HumeTTSConfig",
    "MurfTTSAdapter",
    "MurfTTSConfig",
    "OpenAITTSAdapter",
    "OpenAITTSConfig",
    "RimeTTSAdapter",
    "RimeTTSConfig",
    "SmallestTTSAdapter",
    "SmallestTTSConfig",
]
