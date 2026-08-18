"""Speechmatics voice AI vendor - STT.

Speechmatics provides enterprise-grade speech recognition with support
for 50+ languages and advanced features like speaker diarization.

STT: Real-time streaming via WebSocket with excellent accuracy
Features: Speaker diarization, custom vocabularies, interim results
"""

from .stt import (
    SpeechmaticsLanguages,
    SpeechmaticsModels,
    SpeechmaticsSTT,
    SpeechmaticsSTTStream,
)

__all__ = [
    "SpeechmaticsSTT",
    "SpeechmaticsSTTStream",
    "SpeechmaticsModels",
    "SpeechmaticsLanguages",
]
