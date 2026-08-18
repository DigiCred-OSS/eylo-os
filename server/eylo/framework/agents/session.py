"""Conversation session contracts for framework runs."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject
from .context import RunInput, RunMessage


class SessionSnapshot(FrozenFrameworkModel):
    """Current LLM-visible session state."""

    conversation_id: UUID
    messages: tuple[RunMessage, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)


class Session(Protocol):
    """Protocol for DB-backed conversation memory providers."""

    async def load(self, conversation_id: UUID) -> SessionSnapshot:
        """Load persisted conversation history."""

    async def build_run_input(self, conversation_id: UUID) -> RunInput:
        """Build LLM-visible input for the next model call."""

    async def append_items(
        self,
        conversation_id: UUID,
        items: tuple[RunMessage, ...],
    ) -> None:
        """Persist framework-created messages."""
