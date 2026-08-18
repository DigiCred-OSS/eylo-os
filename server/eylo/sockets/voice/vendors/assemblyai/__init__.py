"""AssemblyAI voice AI vendor - STT with turn detection.

AssemblyAI provides real-time speech recognition with advanced turn detection,
enabling natural conversation understanding.

STT: Universal-Streaming model with turn detection, interim results
"""

from .stt import AssemblyAISTT

__all__ = ["AssemblyAISTT"]
