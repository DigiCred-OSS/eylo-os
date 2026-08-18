# Pipeline catalog

Pipelines coordinate domain modules, provider sockets, durable work, and
transport effects. This is the only backend layer allowed to import both
`eylo.modules` and `eylo.sockets`.

| Pipeline | Responsibility |
| --- | --- |
| `composition.py` | idempotently register pipeline-owned system tools and scheduled actions before serving or polling |
| `agents` | resolve published Agents/config relations, swarm behavior, and provider-config deletion references |
| `conversation` | start and run conversational work, build context, dispatch tools, queue requests, execute background attachments, and converge failures |
| `llm` | construct resolved LLM adapters, normalize transient messages, stream decomposed TTS, and run first-party background implementations |
| `agent_run_tools.py` | project run/input/cancellation controls into system tools |
| `agent_run_transcript.py` | write framework/tool/runtime progress into Agent-run transcript items |
| `parallel_agents` | durable worker dispatch for LLM tasks, swarm members, and attached background Agents |
| `system_tools` | register platform tools and connect them to knowledge, memory, sandbox, telephony, and task pipelines |
| `mcp` | discover and execute MCP tools through pinned server definitions |
| `integrations_v2` | registry, OAuth, credential resolution, origin-pinned HTTP, refresh, durable mutations, and Agent-tool projection for curated vendors |
| `knowledgebase` | resolve vendor/index authority, ingest files/corpora, query with citations/top-k/reranking, and reindex durably |
| `memory` | recall hooks, fact formation, reconciliation, config dependency references, and reindexing |
| `embedding` | verify/delete/resolve embedding configs and build embedding runtime |
| `reranking` | verify/delete/resolve reranking configs and apply optional reranking |
| `storage` | verify/delete/resolve storage configs and enforce platform-built object keys |
| `email` | verify email configs, deliver messages, and execute email tools |
| `voice` | browser/realtime/decomposed voice runtime, activity/interruption policy, transcript facts, recordings, and post-call work |
| `webrtc` | ICE policy, signalling, browser peer/media tracks, and playback |
| `telephony` | carrier config, webhooks, media streams, sessions, call control, number management, and telephony tools |
| `websocket` | public socket authority, connection manager, protocol handlers, and widget event delivery |
| `sandbox` | access/config resolution, objective execution, workspace session/checkpoint reuse, and sandbox tools |
| `scheduler` | turn a claimed occurrence into a durable Agent run |
| `campaigns` | execute one durable campaign contact attempt and consume call outcomes |
| `outbound` | normalize outbound request ownership and receipts used by products |
| `deletions` | ownership-aware call/contact/Agent/memory erasure and durable deletion workflow |
| `durable_events` | compose required durable consumers and expose delivery health |
| `session_timeline.py` | best-effort runtime filing into a user session's durable timeline |
| `widget_development.py` | local-only fixed widget identity resolution |
| `widget_invitations.py` | widget invitation/session pipeline composition |

## Durable workflow registrations

The worker registers these workflow families before it polls:

- Agent runs: message, schedule occurrence, or sandbox objective;
- knowledge ingestion, corpus import, and reindex;
- memory formation, reconciliation, and reindex;
- deletions;
- voice recording upload;
- campaign attempts;
- durable event delivery;
- periodic work.

Product rows are created first. Absurd owns the execution attempt, retry, wait,
and cancellation. A detached worker always reloads its organization-scoped
authority from DB.
