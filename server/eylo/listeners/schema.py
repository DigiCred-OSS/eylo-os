"""Local best-effort conversation UI event schema."""

from eylo.events.schema.py_events.base import BaseEvent
from eylo.modules.conversations.schemas.conversations import (
    ConversationInDb,
)


class ConversationUpdatedEvent(BaseEvent):
    conversation: ConversationInDb
