"""Vendor-agnostic configuration for a realtime voice session.

Built from VoiceConfig + ConversationContext at session start.
Passed to RealtimeFactory and then to the vendor adapter.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.tool_record import ToolRecord


class RealtimeSessionConfig(BaseModel):
    """Everything a vendor adapter needs to open a realtime session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Identity (from WSSessionState + conversation)
    organization_id: UUID
    conversation_id: UUID
    agent_id: UUID
    session_id: str
    voice_session_row_id: UUID | None = None

    # Vendor selection
    vendor: Literal["amazon-nova-sonic", "gemini-live", "openai-realtime"]
    model: str  # e.g. "gemini-3.1-flash-live-preview" or "gpt-4o-realtime-preview"

    # LLM config
    system_prompt: str = ""
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None

    # Voice
    voice: str
    input_transcription_model: str | None = None
    vad_threshold: float | None = None
    vad_silence_ms: int | None = None
    endpointing_sensitivity: Literal["HIGH", "MEDIUM", "LOW"] | None = None

    # Tools — platform format, adapter transforms to vendor format
    tools: list[ToolRecord] = Field(default_factory=list)

    # Gemini: context window compression (D013)
    is_context_compression_enabled: bool | None = None
    context_compression_trigger_tokens: int | None = None
