# Runtime surfaces

## API

`server/eylo/app.py` constructs FastAPI and mounts three router planes below
`/api`: member-private, public, and contact/widget. It also serves static
playground assets and exposes `/health`.

The running OpenAPI document is the request/response reference. Do not maintain
a second handwritten endpoint catalog.

## Durable worker

`python -m eylo.agent_run_worker` registers model metadata, pipeline tools,
listeners, Agent-run executors, every durable workflow, required event
consumers, and periodic work before polling. The API process does not perform
durable jobs in the background as an alternative execution owner.

## Operator console

The authenticated console exposes the repository documentation under
**Resources → Documentation**. The route is organization-scoped so links are
shareable inside the console, while the rendered content remains platform-wide
and comes from `README.md` plus `docs/**/*.md` at build time. Search runs in the
browser; documentation has no DB rows, API controller, or MobX store.

The React console uses public member APIs and generated OpenAPI types.

| Feature folder                                            | Surface                                                                          |
| --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `features/agents`, `features/swarms`                      | Agent drafts/revisions, relations, voice stack, swarm members                    |
| `features/providers`                                      | schema-driven provider catalog, forms, verification, tools, and config lifecycle |
| `features/knowledge`, `features/memory`                   | knowledgebases/jobs/grants and memory inspection                                 |
| `features/integrations`                                   | marketplace, installations, connections, and tool policy                         |
| `features/conversations`, `features/sessions`             | canonical exchanges and cross-conversation user-session timelines                |
| `features/voice`, `features/telephony`                    | voice configs/sessions/recordings, numbers, and calls                            |
| `features/automations`, `features/campaigns`              | schedules and outbound campaign product                                          |
| `features/operations`                                     | Agent runs, event health, voice sessions, and system status                      |
| `features/contacts`, `features/members`, `features/tools` | organization entities and tool catalogs                                          |

MobX stores own canonical client entities and API coordination. The URL owns
shareable list/detail/filter state. Components own transient interaction state.

## Widget SDK

`widget/src/` owns transport and reactive state:

- contact-session consumption after a host bootstrap resolves authority;
- Agent and conversation selection;
- WebSocket protocol and reconnect behavior;
- message, participant, auth, tool, and interface events;
- voice/WebRTC control and media lifecycle;
- conversation-file upload capability.

The SDK does not choose an organization or contact in production. Local-only
fixed identity comes from paired server environment variables.

See the [Widget SDK reference](widget-sdk.md) for its current source API and
distribution status.

## Preact widget UI

`widget/preact-ui/` composes the SDK into the contact journey: Agent list,
conversation list/unread state, message exchange, file upload, connection
authorization signals, and voice controls. The SDK's state machine is
authoritative; the UI does not invent a parallel call lifecycle.

The Preact/host bootstrap exchanges production invitations and starts
local-only development sessions before passing the resulting contact session to
the SDK. See [Use the Widget SDK from Preact](../how-to/use-widget-sdk.md).

## CLI

The CLI reads the live OpenAPI document, discovers resources and actions, and
calls public APIs. It stores base URL, organization ID, and bearer token in its
local config. `--json` preserves machine-readable output; default rendering is
human-oriented.

The CLI never writes platform tables directly.
