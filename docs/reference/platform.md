# Platform and repository map

## Deployable surfaces

| Path | Runtime responsibility |
| --- | --- |
| `server/` | FastAPI API, domain modules, provider sockets, pipelines, PostgreSQL persistence, Redis coordination, and durable worker |
| `web/` | Member-facing React operator console using MobX, Tailwind CSS, and Base UI |
| `widget/` | Headless TypeScript transport/state SDK plus the Preact contact UI |
| `cli/` | OpenAPI-driven command-line client for public platform APIs |
| `infra/docker/eylo/` | Shared API, worker, pgvector/PostgreSQL, and Redis services with explicit development and production overlays |
| `design-system/` | Design references and component showcases; not a production runtime |

## Backend layers

| Layer | Owns | Dependency rule |
| --- | --- | --- |
| `eylo/framework/` | Provider-neutral Agent loop contracts and execution | imports no `eylo.*` platform package |
| `eylo/modules/` | Bounded-context models, domain rules, services, repositories, schemas, and routes | does not import sockets |
| `eylo/sockets/` | Vendor protocols, SDK clients, stream translation, and normalized adapter contracts | does not import modules |
| `eylo/pipelines/` | Cross-layer composition, durable execution, tool dispatch, and transport orchestration | may coordinate modules and sockets |
| `eylo/events/` | Ephemeral event schemas plus durable event domain and persistence | payloads remain bounded and typed |
| `eylo/listeners/` | Explicit in-process Pyventus listener manifest | unordered, concurrent, best-effort reactions |
| `eylo/jobs/` | Small worker entrypoints and task registration imports | delegates behavior to modules/pipelines |
| `eylo/products/` | Consumer-level composition built from platform capabilities | Campaigns is the current product package |

## API security planes

All routes are mounted below `/api`.

| Router | Principal | Boundary |
| --- | --- | --- |
| Private | authenticated member or API key | requested organization must match the authenticated organization; hidden resources return `404` |
| Public | unauthenticated or state-token-specific caller | registration, public session exchange, OAuth callback, webhooks, and transport establishment apply their own checks |
| Widget | authenticated contact session | organization/contact/session authority comes from the widget dependency, not request-selected ownership |

The console and CLI use the member API. The widget uses public session exchange,
widget routes, WebSocket, and WebRTC rather than member credentials.

## Runtime processes

- `eylo.app` registers ORM models, pipeline extensions, and API-process
  listeners before constructing FastAPI.
- The API lifespan owns the WebSocket manager, WebRTC signalling service, and
  DB-pool cleanup.
- `eylo.agent_run_worker` registers all durable workflows before polling the
  shared Absurd queue.
- PostgreSQL is canonical business and durable-work storage.
- Redis supports coordination and live transport state; it is not canonical
  business storage.

## Persistence

`server/alembic/versions/eylo0001_initial_schema.py` is the only migration.
`register_models()` imports every ORM model explicitly so API startup, workers,
Alembic, and standalone verification see the same metadata.

Organization-owned models carry an `organization_id`. Cross-resource foreign
keys include ownership columns when a relationship must not cross tenants.
Soft deletion preserves histories where product ownership requires it.

## Contract authorities

- Generated OpenAPI: HTTP paths and schemas.
- Catalogs: supported provider identifiers and selectable fields.
- Factories: adapter executability.
- Published definition revisions: Agent, template, MCP, schedule, and campaign
  runtime authority.
- Durable rows: Agent-run, ingestion, memory, deletion, campaign, event, and
  recording state.
