# Operate durable work

PostgreSQL is the durable source of truth. Absurd owns queue claims, retries,
waits, cancellation, and worker execution.

## Confirm the worker is running

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  ps
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  logs --since=10m worker
```

Startup logs should show the Agent-run workflow and queue registration. A
missing Absurd queue relation is a migration/runtime mismatch, not a transient
Agent failure.

## Inspect work from the console

- **Operations → Agent runs**: origin, lifecycle, steps, usage, waits, result.
- **Operations → Events**: durable delivery and dead-letter state.
- **Operations → Voice sessions**: live/canonical transcript and recording.
- **Platform → Knowledge/Memory**: ingestion, formation, reconciliation, and
  reindex state.
- **Platform → Automations** and **Products → Outbound → Campaigns**:
  occurrences and attempts.

## Handle an input wait

An Agent run may enter `waiting_for_input` or `waiting_for_approval`. The run is
durably checkpointed and releases compute. A user response is written first,
then wakes the named durable wait. There is no timeout merely because the user
has not answered.

## Cancel work

Use the owning module's API or console action. Cancellation is persisted before
the durable engine is signalled. Do not delete queue rows or force a lifecycle
state in SQL.

## Diagnose retries

Inspect the product job and Agent run first, then the worker log. Distinguish:

- retryable provider/network failure;
- deterministic validation or extraction failure;
- missing configuration;
- exhausted execution budget;
- cancellation;
- dead-lettered durable event consumer.

The queue is an execution authority, not the product audit projection.
