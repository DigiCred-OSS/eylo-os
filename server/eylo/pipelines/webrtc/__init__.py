"""WebRTC media and signaling pipeline orchestration."""

from eylo.pipelines.webrtc.singleton import (
    S_webrtc_signaling,
    start_webrtc_signaling,
    stop_webrtc_signaling,
)

__all__ = [
    "S_webrtc_signaling",
    "start_webrtc_signaling",
    "stop_webrtc_signaling",
]
