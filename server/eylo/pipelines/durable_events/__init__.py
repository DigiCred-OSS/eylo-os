"""Durable event consumer composition and operational API."""

from eylo.pipelines.durable_events.manifest import (
    build_event_consumer_registry,
    durable_event_consumer_manifest,
)

__all__ = [
    "build_event_consumer_registry",
    "durable_event_consumer_manifest",
]
