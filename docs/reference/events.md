# Events and delivery contracts

Eylo has two event mechanisms with different guarantees.

## Ephemeral local events

Pyventus listeners are registered from one explicit manifest in API and worker
processes.

- Delivery: concurrent, unordered, best effort, in process.
- Storage: none.
- Use: live UI deltas, transport/call state broadcasts, and module
  observability.
- Failure: contained by the emitter/listener path; no retry or replay contract.

The manifest currently covers:

- Agent inference, processing, tool execution, and response completion;
- message, conversation, and participant changes;
- WebRTC, STT, and TTS state;
- call lifecycle and integration-connection state;
- knowledgebase lifecycle, grant, ingestion, corpus, query, and reindex facts;
- memory fact, formation, reconciliation, reindex, and recall facts.

Knowledge and memory events are intentionally ephemeral in V1.

## Durable events

Durable events are organization-visible facts and required-consumer triggers.
They are not a replacement for audit logs.

| Table | Contract |
| --- | --- |
| `event_outbox` | immutable bounded event envelope |
| `event_deliveries` | independent state per required consumer |
| `event_inbox_receipts` | exactly one receipt for a committed consumer transition |

Delivery lifecycle: `pending` → `running` → `succeeded` or `dead_letter`.
Events are filed in the source transaction. After commit, Absurd executes each
required delivery. A consumer receipt prevents the same event/consumer pair
from committing twice.

Current required consumers derive campaign call outcomes and canonical voice
segments from durable voice facts.

## User-session timeline facts

The session UI projects an allowlisted subset of durable events. The correlation
ID is the user-session ID; a conversation may appear in multiple sessions and a
session may observe multiple conversations.

Categories:

- session;
- conversation;
- message;
- Agent;
- tool;
- file;
- voice;
- telephony;
- technical transport/provider state.

Payload keys are allowlisted per event type. Display projections exclude
message text, contact identifiers, credentials, provider payloads, transcript
content, and other unbounded PII.

## Ordering

Neither mechanism promises global event ordering. Durable envelopes retain
`occurred_at`, `recorded_at`, correlation, and causation so a projection can
build an explanatory timeline without treating insertion order as business
truth.
