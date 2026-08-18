"""Adapters from existing Eylo domain schemas to framework primitives."""

from .conversation_runner import ExistingConversationModel, FrameworkConversationRunner
from .domain import (
    agent_spec_from_context,
    agent_spec_from_indb,
    run_input_from_context,
    run_message_from_indb,
    tool_spec_from_indb,
)
from .tool_executor import PlatformToolExecutor

__all__ = [
    "PlatformToolExecutor",
    "ExistingConversationModel",
    "FrameworkConversationRunner",
    "agent_spec_from_context",
    "agent_spec_from_indb",
    "run_input_from_context",
    "run_message_from_indb",
    "tool_spec_from_indb",
]
