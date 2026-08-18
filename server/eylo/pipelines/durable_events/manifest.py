"""Exact composition of every required durable event consumer."""

from __future__ import annotations

from eylo.events.durable.registry import EventConsumerKey, EventConsumerRegistry
from eylo.pipelines.campaigns import register_campaign_call_outcome_consumer
from eylo.pipelines.voice.transcript_facts import register_voice_transcript_consumers


def build_event_consumer_registry() -> EventConsumerRegistry:
    """Compose the same exact consumer registry in each durable worker."""
    registry = EventConsumerRegistry()
    register_campaign_call_outcome_consumer(registry)
    register_voice_transcript_consumers(registry)
    return registry


def durable_event_consumer_manifest() -> tuple[EventConsumerKey, ...]:
    """Return the exact identities produced by current worker composition."""
    return build_event_consumer_registry().manifest()


__all__ = [
    "build_event_consumer_registry",
    "durable_event_consumer_manifest",
]
