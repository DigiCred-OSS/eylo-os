"""Errors for the `voice` domain."""

class RealtimeVoiceDisabledError(Exception):
    """Raised when realtime voice is requested while the feature is disabled."""


class VoiceConfigError(Exception):
    """Base error for organization-owned Voice Config definitions."""


class VoiceConfigNotFound(VoiceConfigError):
    """Raised without revealing whether an id exists in another organization."""


class VoiceConfigConflict(VoiceConfigError):
    """Raised when an optimistic Voice Config edit observes stale state."""


class VoiceConfigInUse(VoiceConfigError):
    """Raised when a Voice Config is still bound to an Agent."""
