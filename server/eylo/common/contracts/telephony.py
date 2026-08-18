"""Vendor-neutral telephony outcome values."""

from enum import Enum


class CallEndedReason(str, Enum):
    """Why a call ended, for events, analytics and retry policy."""

    AGENT_ENDED_CALL = "agent_ended_call"
    AGENT_ENDED_CALL_AFTER_MESSAGE = "agent_ended_call_after_message"
    AGENT_SAID_END_CALL_PHRASE = "agent_said_end_call_phrase"
    AGENT_FORWARDED_CALL = "agent_forwarded_call"

    CUSTOMER_ENDED_CALL = "customer_ended_call"
    CUSTOMER_BUSY = "customer_busy"
    CUSTOMER_DID_NOT_ANSWER = "customer_did_not_answer"

    EXCEEDED_MAX_DURATION = "exceeded_max_duration"
    SILENCE_TIMED_OUT = "silence_timed_out"

    ERROR_SYSTEM = "error_system"
    ERROR_STT_FAILED = "error_stt_failed"
    ERROR_LLM_FAILED = "error_llm_failed"
    ERROR_TTS_FAILED = "error_tts_failed"
    ERROR_PROVIDER_DISCONNECTED = "error_provider_disconnected"

    VOICEMAIL_DETECTED = "voicemail_detected"
    MANUALLY_CANCELED = "manually_canceled"
    UNKNOWN = "unknown"
