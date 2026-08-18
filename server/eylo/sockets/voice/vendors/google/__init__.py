"""Google Cloud voice AI vendor - STT.

Google Cloud provides enterprise-grade speech recognition with support
for 125+ languages and variants.

STT: Streaming Recognition via gRPC with excellent accuracy
Features: Speaker diarization, automatic punctuation, profanity filtering
"""

from .stt import GoogleLanguages, GoogleModels, GoogleSTT, GoogleSTTStream

__all__ = [
    "GoogleSTT",
    "GoogleSTTStream",
    "GoogleModels",
    "GoogleLanguages",
]
