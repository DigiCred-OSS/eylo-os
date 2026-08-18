"""Stable durable fact identities for canonical voice transcript projection."""

VOICE_MESSAGE_SUBJECT_TYPE = "conversation.message"
VOICE_MESSAGE_EVENT_TYPE = "voice.message.finalized"
VOICE_MESSAGE_EVENT_VERSION = 1
VOICE_MESSAGE_SEGMENT_CONSUMER = "voice.message_segment"

VOICE_SESSION_SUBJECT_TYPE = "voice.session"
VOICE_SESSION_ENDED_EVENT_TYPE = "voice.session.ended"
VOICE_SESSION_ENDED_EVENT_VERSION = 1
VOICE_SESSION_COMPLETION_CONSUMER = "voice.session_completion"

VOICE_RECORDING_SUBJECT_TYPE = "voice.recording"
VOICE_RECORDING_AVAILABLE_EVENT_TYPE = "voice.recording.available"
VOICE_RECORDING_AVAILABLE_EVENT_VERSION = 1
VOICE_RECORDING_ATTACHMENT_CONSUMER = "voice.recording_attachment"

__all__ = [name for name in globals() if name.startswith("VOICE_")]
