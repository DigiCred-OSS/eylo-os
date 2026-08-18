# Events and durable work

Events say that something happened. Durable work says that an effect must be
attempted until it reaches a terminal state. Eylo keeps those responsibilities
distinct even when one starts the other.

## Commit before reaction

A canonical write happens in the owning transaction. An event that describes
that write is emitted or filed only when its source can no longer roll back.
This prevents listeners and workers from observing state that never committed.

For durable events, the outbox envelope is written in the source transaction.
Post-commit binding creates/wakes Absurd work for each required delivery.

## Ephemeral events

Local events are useful when every consumer is best-effort: broadcast a new
message, update connection state, or observe knowledge/memory lifecycle. They
execute concurrently without ordering or replay.

An ephemeral listener must not be the only owner of a required durable effect.

## Durable events

Durable events are user-visible organization facts that may also require
consumers. Each consumer has independent state and an exact inbox receipt.
Dead-letter state is visible to operators.

The event record is not the whole audit system: it intentionally carries a
bounded, privacy-safe payload rather than copying arbitrary domain or provider
data.

## Durable jobs

Ingestion, formation, reindexing, recording upload, deletion, campaign attempts,
and Agent runs own product job rows. Queue messages are not canonical status.
Absurd claims the exact persisted work, applies retries/cancellation/waits, and
updates product state through the owning service.

This makes DB rows explainable even if a queue delivery is duplicated or a
worker restarts.
