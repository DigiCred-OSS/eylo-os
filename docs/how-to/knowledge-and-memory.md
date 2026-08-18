# Operate knowledge and memory

Knowledge and memory both use embedding spaces, but they own different facts.
Knowledge stores source-derived chunks. Memory stores compact Agent-, contact-,
or conversation-owned facts formed during use.

## Configure retrieval

1. Create and verify an embedding provider configuration.
2. Optionally create and verify a reranking configuration.
3. Create and verify a memory provider configuration when memory is needed.
4. Bind the selected IDs and revisions explicitly; no global default exists.

## Create an organization knowledgebase

1. Open **Platform → Knowledge**.
2. Create a knowledgebase and choose its embedding configuration.
3. Grant an Agent read or read/write access.
4. Upload a supported file or submit an object already owned by storage.
5. Wait for the ingestion job to succeed.
6. Query through the Agent and inspect returned citations.

Every chunk carries its knowledgebase identity. Grants never widen to another
knowledgebase at the same organizational scope.

## Use conversation files

Enable **Allow file uploads** on the Agent. The widget then accepts files
without asking the contact for a destination. Eylo lazily treats the
conversation ID as the conversation-scoped knowledgebase, writes the file under
that authority, ingests it, and exposes it through the normal knowledge tools.

## Inspect memory

Open **Platform → Memory** to inspect active and expired facts, owner level,
source, confidence, recall count, expiry, index state, relationships, and
conflicts. Agent tools expose remember, refresh, forget, and recall behavior;
formation and reconciliation run asynchronously.

## Reindex after embedding changes

An embedding config ID or revision change marks dependent knowledge and memory
indexes invalid. Start reindexing from each affected resource. Queries must not
mix vectors from different embedding spaces.
