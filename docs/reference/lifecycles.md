# Lifecycle states

This page summarizes operator-visible state machines. Domain enums and DB
constraints remain authoritative.

## Provider configuration

```text
create/update -> unverified -> verify -> ready
ready --disable--> not ready
ready --update--> new unverified revision
any current revision --delete--> disabled + soft-deleted
```

Readiness also requires credentials to remain available and the revision to be
current.

## Agent definition

An Agent starts as a draft. Publication creates an immutable usable revision.
Editing changes only the draft. Withdrawal prevents new resolution; revision
revocation targets one published revision. Runtime never executes a draft.

## Agent run

`queued` → `running` → one of:

- `waiting_for_input` → answer → `running`;
- `waiting_for_approval` → approval → `running`;
- `completed`;
- `failed`;
- `cancelled`.

Outcomes are `achieved`, `unachievable`, `failed`, `cancelled`, or `exhausted`.
Steps independently move through pending, running, completed, failed, or
cancelled.

## Message request

```text
PENDING -> PROCESSING -> AWAITING_TOOL_RESULTS -> PROCESSING -> COMPLETED
```

Processing may end as failed, interrupted, or skipped. Invalid transitions are
logged and ignored so they do not roll back unrelated canonical writes.
Interrupted and skipped requests are excluded from future model context.

## User session

`active` → `disconnected` → `active` on reconnect, or `ended`/`failed` as a
terminal state. The connection sequence increases across reconnects. A session
may reference multiple conversations.

## Knowledge and memory indexes

Both expose `active`, `reindex_required`, `reindexing`, and `failed`. A changed
embedding config ID/revision moves the dependent index out of `active` until a
successful reindex publishes the new space.

Knowledge ingestion, corpus import, memory formation, reconciliation, and
reindex jobs persist pending/running/terminal attempts separately from the
resource's index state.

## Voice session and recording

Voice sessions are active, completed, or failed. Canonical transcript state is
`not_run`, `clean`, `redacted`, `failed`, or `no_storage`. Runtime mode is
browser decomposed, browser realtime, or telephony.

Recording upload is secondary durable work: queued/running output becomes
available or failed without interrupting the already completed live call.

## Campaign

Campaigns move through `draft`, `scheduled`, `running`, `paused`, `completed`,
or `canceled`. Per-contact attempts move independently through pending, queued,
in-progress, completed, failed, retry, skipped, or cancelled. Preparation
warnings allow V1 outreach; blockers prevent start.

## Durable event delivery

`pending` → `running` → `succeeded` or `dead_letter`. An inbox receipt proves
the exact consumer transition committed.
