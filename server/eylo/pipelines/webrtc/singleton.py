"""Process-local runtime access for the `webrtc` pipeline."""

# Singleton instance
from eylo.pipelines.webrtc.signaling_manager import WebRTCSignalingManager

S_webrtc_signaling = WebRTCSignalingManager()


# Lifecycle functions
async def start_webrtc_signaling():
    """Start the WebRTC signaling service."""
    await S_webrtc_signaling.start()


async def stop_webrtc_signaling():
    """Stop the WebRTC signaling service."""
    await S_webrtc_signaling.stop()


__all__ = [
    "S_webrtc_signaling",
    "start_webrtc_signaling",
    "stop_webrtc_signaling",
]
