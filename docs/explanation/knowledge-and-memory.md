# Knowledge and memory

Knowledge and memory both retrieve relevant text, but they answer different
ownership questions.

## Knowledge is source-owned

A knowledgebase owns files, chunks, grants, embedding authority, and citations.
Ingestion deterministically extracts supported text, chunks it, embeds it, and
replaces the same source identity on retry. Query returns source references so
an Agent can cite where an answer came from.

An organization knowledgebase may be read-only or writable for a given Agent.
A conversation knowledgebase is created lazily from the conversation ID when
the Agent permits file uploads. The contact never selects an internal
destination.

## Memory is experience-owned

Memory stores compact facts learned during use. Ownership is typed:

- Agent memory helps the Agent retain reusable learning;
- contact memory helps the Agent serve one person consistently;
- conversation memory supports an extended exchange.

Recall happens before a turn. Formation proposes facts after relevant
conversation work. Reconciliation detects duplicates and conflicts in the
background. Facts retain provenance, status, expiry, relationships, and index
state so operators can understand what was learned and why.

## Shared retrieval infrastructure

Both systems can use embedding and optional reranking configurations. The
embedding config ID and revision define a vector space. Changing either makes
previous vectors invalid until reindexing finishes.

The systems do not merge stores merely because they share an organization,
scope label, or embedding provider. Every chunk/fact query retains its owning
knowledgebase or typed memory owner.

## Why post-call/async formation

Knowledge ingestion and memory formation are secondary to the live product
flow. They persist jobs, execute durably, and expose failure without blocking a
conversation or call. This keeps the Agent responsive and makes retries
idempotent and inspectable.
