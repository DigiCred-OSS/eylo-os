"""Conversation-module exports for cross-layer constants."""

from eylo.common.contracts.conversation import (
    HANDOFF_TOOL_PREFIX as HANDOFF_TOOL_PREFIX,
)
from eylo.common.contracts.conversation import (
    REALTIME_MESSAGE_SOURCE as REALTIME_MESSAGE_SOURCE,
)
from eylo.common.contracts.conversation import WIDGET_TOOL_PREFIX as WIDGET_TOOL_PREFIX

DELETED_CONTACT_ENTITY_ID = "deleted contact"

__all__ = [
    "DELETED_CONTACT_ENTITY_ID",
    "HANDOFF_TOOL_PREFIX",
    "REALTIME_MESSAGE_SOURCE",
    "WIDGET_TOOL_PREFIX",
]
