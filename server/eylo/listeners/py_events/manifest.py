"""Explicit process manifest for bounded local Pyventus listeners."""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel
from pyventus.events import EventSubscriber

from eylo.events.py_events.emitter import EyloLinker, _get_event_emitter
from eylo.events.schema.py_events.base import (
    AgentProcessingEvent,
    AgentResponseCompleteEvent,
    AgentRunInferenceEvent,
    AgentRunToolEvent,
    AgentToolResponseEvent,
    AuthRequiredEvent,
    ConversationCreatedEvent,
    MessageCreatedEvent,
    ParticipantCreatedEvent,
)
from eylo.events.schema.py_events.call import (
    CallConnectedEvent,
    CallEndedEvent,
    CallRingingEvent,
    CallStartedEvent,
    CallTransferredEvent,
    CallTransferringEvent,
)
from eylo.events.schema.py_events.connections import (
    ConnectionExpiredEvent,
    ConnectionFailedEvent,
    ConnectionStartedEvent,
    ConnectionSuccessEvent,
)
from eylo.events.schema.py_events.knowledgebase import (
    KnowledgeCorpusImportLifecycleEvent,
    KnowledgeIngestionLifecycleEvent,
    KnowledgeQueryObservedEvent,
    KnowledgeReindexLifecycleEvent,
    KnowledgebaseAccessChangedEvent,
    KnowledgebaseLifecycleEvent,
)
from eylo.events.schema.py_events.memory import (
    MemoryFactsChangedEvent,
    MemoryFormationLifecycleEvent,
    MemoryRecallObservedEvent,
    MemoryReconciliationLifecycleEvent,
    MemoryReindexLifecycleEvent,
)
from eylo.events.schema.py_events.voice import (
    STTStateEvent,
    TTSStateEvent,
    WebRTCStateEvent,
)
from eylo.listeners.py_events.agent_lifecycle import (
    handle_agent_processing,
    handle_agent_response_complete,
    handle_agent_thinking,
    handle_tool_completed,
    handle_tool_executing,
)
from eylo.listeners.py_events.auth import broadcast_auth_required
from eylo.listeners.py_events.call_lifecycle import (
    handle_call_connected,
    handle_call_ended,
    handle_call_ringing,
    handle_call_started,
    handle_call_transferred,
    handle_call_transferring,
)
from eylo.listeners.py_events.connections import (
    broadcast_connection_expired,
    broadcast_connection_failed,
    broadcast_connection_started,
    broadcast_connection_success,
)
from eylo.listeners.py_events.conversations import (
    broadcast_created_conversation,
    broadcast_updated_conversation,
)
from eylo.listeners.py_events.knowledgebase import observe_knowledge_event
from eylo.listeners.py_events.memory import observe_memory_event
from eylo.listeners.py_events.messages import (
    broadcast_created_message,
)
from eylo.listeners.py_events.participants import handle_participant_created
from eylo.listeners.py_events.voice_lifecycle import (
    handle_stt_state,
    handle_tts_state,
    handle_webrtc_state,
)
from eylo.listeners.schema import ConversationUpdatedEvent

LOCAL_LISTENER_MANIFEST_VERSION = 1
_HANDLER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")

LocalHandler = Callable[[BaseModel], Awaitable[None]]


class ListenerManifestError(Exception):
    """The explicit local listener manifest is incomplete or ambiguous."""


class ListenerProcessRole(StrEnum):
    API = "api"
    WORKER = "worker"
    VERIFIER = "verifier"


class ListenerRole(StrEnum):
    UI_DELTA = "ui_delta"
    RUNTIME_HOOK = "runtime_hook"
    OBSERVABILITY = "observability"


class ListenerDeliveryClass(StrEnum):
    EPHEMERAL = "ephemeral.concurrent_unordered_best_effort"


ALL_PROCESS_ROLES = frozenset(ListenerProcessRole)


@dataclass(frozen=True, slots=True)
class ListenerRegistration:
    """One stable local handler contract."""

    handler_id: str
    event_type: type[BaseModel]
    event_version: int
    role: ListenerRole
    delivery_class: ListenerDeliveryClass
    process_roles: frozenset[ListenerProcessRole]
    handler: LocalHandler

    def __post_init__(self) -> None:
        if not _HANDLER_ID_PATTERN.fullmatch(self.handler_id):
            raise ListenerManifestError(
                f"Invalid local listener handler ID {self.handler_id!r}."
            )
        if not 1 <= self.event_version <= 32_767:
            raise ListenerManifestError("Local event version must be 1-32767.")
        if not self.process_roles:
            raise ListenerManifestError(
                "Local listener has no applicable process role."
            )
        if not isinstance(self.event_type, type) or not issubclass(
            self.event_type,
            BaseModel,
        ):
            raise ListenerManifestError("Local listener event type must be a model.")
        if not callable(self.handler):
            raise ListenerManifestError("Local listener handler must be callable.")

    @property
    def event_name(self) -> str:
        return self.event_type.__name__


@dataclass(frozen=True, slots=True)
class ListenerManifestHealth:
    """Safe process-visible projection of exact local registrations."""

    manifest_version: int
    process_role: ListenerProcessRole
    delivery_class: ListenerDeliveryClass
    healthy: bool
    handler_count: int
    event_count: int
    handler_ids: tuple[str, ...]


def _entry(
    handler_id: str,
    event_type: type[BaseModel],
    handler: LocalHandler,
    role: ListenerRole,
) -> ListenerRegistration:
    return ListenerRegistration(
        handler_id=handler_id,
        event_type=event_type,
        event_version=1,
        role=role,
        delivery_class=ListenerDeliveryClass.EPHEMERAL,
        process_roles=ALL_PROCESS_ROLES,
        handler=handler,
    )


LISTENER_MANIFEST = (
    _entry(
        "local.auth.required.v1",
        AuthRequiredEvent,
        broadcast_auth_required,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.agent.thinking.v1",
        AgentRunInferenceEvent,
        handle_agent_thinking,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.agent.processing.v1",
        AgentProcessingEvent,
        handle_agent_processing,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.agent.tool_executing.v1",
        AgentRunToolEvent,
        handle_tool_executing,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.agent.tool_completed.v1",
        AgentToolResponseEvent,
        handle_tool_completed,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.agent.response_complete.v1",
        AgentResponseCompleteEvent,
        handle_agent_response_complete,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.message.created.v1",
        MessageCreatedEvent,
        broadcast_created_message,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.conversation.created.v1",
        ConversationCreatedEvent,
        broadcast_created_conversation,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.conversation.updated.v1",
        ConversationUpdatedEvent,
        broadcast_updated_conversation,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.voice.webrtc_state.v1",
        WebRTCStateEvent,
        handle_webrtc_state,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.voice.stt_state.v1",
        STTStateEvent,
        handle_stt_state,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.voice.tts_state.v1",
        TTSStateEvent,
        handle_tts_state,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.participant.created.v1",
        ParticipantCreatedEvent,
        handle_participant_created,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.call.started.v1",
        CallStartedEvent,
        handle_call_started,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.call.ringing.v1",
        CallRingingEvent,
        handle_call_ringing,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.call.connected.v1",
        CallConnectedEvent,
        handle_call_connected,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.call.ended.v1", CallEndedEvent, handle_call_ended, ListenerRole.UI_DELTA
    ),
    _entry(
        "local.call.transferring.v1",
        CallTransferringEvent,
        handle_call_transferring,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.call.transferred.v1",
        CallTransferredEvent,
        handle_call_transferred,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.connection.started.v1",
        ConnectionStartedEvent,
        broadcast_connection_started,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.connection.success.v1",
        ConnectionSuccessEvent,
        broadcast_connection_success,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.connection.failed.v1",
        ConnectionFailedEvent,
        broadcast_connection_failed,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.connection.expired.v1",
        ConnectionExpiredEvent,
        broadcast_connection_expired,
        ListenerRole.UI_DELTA,
    ),
    _entry(
        "local.knowledgebase.lifecycle.v1",
        KnowledgebaseLifecycleEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.knowledgebase.access.v1",
        KnowledgebaseAccessChangedEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.knowledge.ingestion.lifecycle.v1",
        KnowledgeIngestionLifecycleEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.knowledge.corpus_import.lifecycle.v1",
        KnowledgeCorpusImportLifecycleEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.knowledge.reindex.lifecycle.v1",
        KnowledgeReindexLifecycleEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.knowledge.query.observed.v1",
        KnowledgeQueryObservedEvent,
        observe_knowledge_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.memory.facts.changed.v1",
        MemoryFactsChangedEvent,
        observe_memory_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.memory.formation.lifecycle.v1",
        MemoryFormationLifecycleEvent,
        observe_memory_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.memory.reconciliation.lifecycle.v1",
        MemoryReconciliationLifecycleEvent,
        observe_memory_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.memory.reindex.lifecycle.v1",
        MemoryReindexLifecycleEvent,
        observe_memory_event,
        ListenerRole.OBSERVABILITY,
    ),
    _entry(
        "local.memory.recall.observed.v1",
        MemoryRecallObservedEvent,
        observe_memory_event,
        ListenerRole.OBSERVABILITY,
    ),
)

_registered_pid: int | None = None
_subscribers: dict[str, EventSubscriber] = {}
_last_health: ListenerManifestHealth | None = None


def setup_listener_manifest(
    *,
    process_role: ListenerProcessRole,
) -> ListenerManifestHealth:
    """Register and validate the exact listener set for this process."""
    global _last_health, _registered_pid, _subscribers

    entries = _applicable_entries(process_role)
    _validate_entries(entries)
    _get_event_emitter()
    current_pid = os.getpid()
    if _registered_pid != current_pid:
        EyloLinker.remove_all()
        _subscribers = {
            entry.handler_id: EyloLinker.subscribe(
                entry.event_type,
                event_callback=entry.handler,
            )
            for entry in entries
        }
        _registered_pid = current_pid

    _validate_registry(entries, _subscribers)
    _last_health = ListenerManifestHealth(
        manifest_version=LOCAL_LISTENER_MANIFEST_VERSION,
        process_role=process_role,
        delivery_class=ListenerDeliveryClass.EPHEMERAL,
        healthy=True,
        handler_count=len(entries),
        event_count=len({entry.event_name for entry in entries}),
        handler_ids=tuple(sorted(entry.handler_id for entry in entries)),
    )
    return _last_health


def listener_manifest_health() -> ListenerManifestHealth | None:
    """Return the latest validated process projection, if setup ran."""
    return _last_health


def _applicable_entries(
    process_role: ListenerProcessRole,
) -> tuple[ListenerRegistration, ...]:
    return tuple(
        entry for entry in LISTENER_MANIFEST if process_role in entry.process_roles
    )


def _validate_entries(entries: tuple[ListenerRegistration, ...]) -> None:
    handler_ids = tuple(entry.handler_id for entry in entries)
    if len(handler_ids) != len(set(handler_ids)):
        raise ListenerManifestError("Local listener handler IDs are duplicated.")
    bindings = tuple((entry.event_type, entry.handler) for entry in entries)
    if len(bindings) != len(set(bindings)):
        raise ListenerManifestError("Local event/handler bindings are duplicated.")


def _validate_registry(
    entries: tuple[ListenerRegistration, ...],
    subscribers: dict[str, EventSubscriber],
) -> None:
    expected_ids = {entry.handler_id for entry in entries}
    if set(subscribers) != expected_ids:
        raise ListenerManifestError(
            "Local subscriber handles do not match the manifest."
        )

    expected: dict[str, set[EventSubscriber]] = {}
    for entry in entries:
        expected.setdefault(entry.event_name, set()).add(subscribers[entry.handler_id])
    actual = EyloLinker.get_registry()
    if actual != expected:
        raise ListenerManifestError(
            "Pyventus registry membership does not match the local manifest."
        )


__all__ = [
    "LISTENER_MANIFEST",
    "LOCAL_LISTENER_MANIFEST_VERSION",
    "ListenerDeliveryClass",
    "ListenerManifestError",
    "ListenerManifestHealth",
    "ListenerProcessRole",
    "ListenerRegistration",
    "ListenerRole",
    "listener_manifest_health",
    "setup_listener_manifest",
]
