# Eylo

Eylo is a self-hosted platform for building, operating, and observing AI
agents. Organizations bring their own model, voice, storage, and integration
providers; Eylo supplies the agent runtime and the product workflows around
them.

The repository contains the complete application:

- `server/` — FastAPI API, agent runtime, PostgreSQL persistence, Redis, and
  Absurd-backed durable work.
- `web/` — React operator console built with MobX, Tailwind CSS, and Base UI.
- `widget/` — embeddable TypeScript SDK plus a Preact chat and voice UI.
- `cli/` — human-friendly client generated from the running API contract.
- `infra/docker/eylo/` — shared Docker services plus explicit development and
  production overlays for the API, worker, PostgreSQL with pgvector, and Redis.

## What Eylo supports

- Conversational and background agents with immutable published revisions.
- Text and voice conversations, messages, participant sessions, recordings,
  and operator-visible timelines.
- LLM, STT, TTS, realtime, WebRTC, telephony, email, storage, embedding,
  reranking, memory, and sandbox provider configurations.
- Voice configuration independent of vendor-specific capabilities, including
  interruption, silence, duration, recording, and call-control policies.
- Organization and conversation knowledgebases with ingestion, citations,
  top-k retrieval, pgvector search, and optional reranking.
- Agent, contact, and conversation memory with formation, reconciliation,
  expiry, and reindexing.
- Curated integrations, per-user or organization-owned connections, MCP
  servers, and per-agent tool grants.
- Campaigns, schedules, swarms, handoffs, and durable agent runs.

Nothing is preconfigured. Eylo never silently selects a vendor, model, or
credential. Configure the capabilities an organization needs, then bind those
capabilities and tools to a published agent.

## Documentation

The [platform documentation](docs/README.md) follows Diátaxis:

- [tutorials](docs/tutorials/first-agent.md) teach the platform through a
  working Agent;
- [how-to guides](docs/how-to/README.md) cover operator and maintainer tasks;
- [reference](docs/reference/README.md) catalogs modules, providers, events,
  lifecycles, and runtime surfaces;
- [Widget SDK](docs/reference/widget-sdk.md) documents the headless runtime,
  with a [Preact integration guide](docs/how-to/use-widget-sdk.md) grounded in
  the working widget;
- [explanation](docs/explanation/README.md) describes the architecture and
  design choices;
- [architecture](docs/diagrams/architecture.md) and
  [data-flow](docs/diagrams/data-flows.md) diagrams map the current runtime.

Signed-in organization members can read the same source-backed pages in the
operator console under **Resources → Documentation**. The console does not
maintain a second documentation copy; each build renders these Markdown files.

The running OpenAPI document at `/docs` remains authoritative for exact HTTP
paths and schemas.

## Architecture

The backend keeps domain and provider concerns separate:

| Layer             | Responsibility                                     |
| ----------------- | -------------------------------------------------- |
| `eylo/framework/` | Standalone, platform-neutral agent loop            |
| `eylo/modules/`   | Domain models, rules, services, and HTTP contracts |
| `eylo/sockets/`   | Vendor protocol adapters                           |
| `eylo/pipelines/` | Cross-layer orchestration and durable effects      |
| `eylo/listeners/` | In-process event reactions                         |
| `eylo/products/`  | Product-level composition                          |

`modules/` and `sockets/` do not import one another. A flow that needs both
belongs in `pipelines/`. The framework has no dependency on the Eylo platform.

## Run locally with Docker

Requirements:

- Docker with Compose
- Node.js 24 or newer and pnpm 11 for the console and widget
- Python 3.13 and uv for direct backend or CLI development

Create the ignored Docker environment file:

```bash
cp server/eylo/common/config/.env.example \
  server/eylo/common/config/.env.docker
openssl rand -hex 32
```

Paste the generated 64-character value into `ENCRYPTION_KEY` in
`server/eylo/common/config/.env.docker`. Generate a separate auth secret for
anything beyond disposable local development.

Start the API, worker, PostgreSQL, and Redis:

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  up -d --build
```

Only the API is published, on the host loopback interface. PostgreSQL and
Redis remain on the Compose network and have no host port mapping. Hosted
deployments use the separate production overlay described in
[Deploy with Docker](docs/how-to/deploy-with-docker.md); do not run the base
file by itself.

The API is available at `http://127.0.0.1:8000`; its interactive contract is at
`http://127.0.0.1:8000/docs`.

Start the operator console in a second terminal:

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev
```

The console is available at `http://127.0.0.1:5173`.

Start the widget in a third terminal:

```bash
cd widget
pnpm install --frozen-lockfile
pnpm build
cd preact-ui
pnpm dev
```

The widget is available at `http://127.0.0.1:5174`.

Register the first member in the console, or use the CLI from the checkout:

```bash
uv run --project cli eylo configure --base-url http://127.0.0.1:8000
uv run --project cli eylo auth register
uv run --project cli eylo auth login
uv run --project cli eylo api-surface
```

Registration creates an organization for the first member. Additional members
join through invitations; Eylo deliberately has organization membership rather
than role-based access control.

## Development

Install backend dependencies and run the API directly:

```bash
cd server
uv sync
uv run alembic upgrade head
uv run fastapi dev main.py
```

Run the durable worker separately:

```bash
cd server
uv run python -m eylo.agent_run_worker
```

Useful local checks:

```bash
cd server
uv run python scripts/verify_documentation.py
uv run ruff check eylo ../cli --extend-ignore F401,F403,F811,E712

cd ../web
pnpm lint
pnpm exec tsc -b --pretty false
pnpm exec vite build

cd ../widget
pnpm build
pnpm --dir preact-ui build
```

The repository intentionally ships no test suite and no hosted CI workflow.
Runtime changes must be exercised through the exact affected path against real
types and disposable infrastructure. Local lint and build gates live in
`.pre-commit-config.yaml`.

## How to add a provider vendor

Provider support is a complete vertical path, not a catalog label.

1. Add the vendor identifier, supported models/voices/options, and config fields
   to the owning capability catalog.
2. Implement the existing provider-neutral protocol under
   `server/eylo/sockets/<capability>/`.
3. Register the adapter in the capability factory. Missing credentials must
   fail explicitly; never fall back to another vendor.
4. Keep config lifecycle in the owning config module; wire cross-layer runtime
   resolution and a bounded real-provider verification in the appropriate
   `server/eylo/pipelines/` boundary.
5. Add the schema-driven form fields to
   `server/eylo/modules/provider_onboarding/catalog.py`. The console consumes
   this catalog; a vendor-specific React form is normally unnecessary.
6. Connect any provider-enabled system tools to explicit organization, Agent,
   and runtime requirements.
7. Create, verify, enable, bind, publish, and execute the provider through the
   public product path. Exercise timeout/cancellation cleanup and cross-org
   isolation.
8. Update the [provider reference](docs/reference/providers.md) and record what
   was and was not tested against the live vendor.

`modules/` and `sockets/` never import one another. Cross-layer construction
belongs in `pipelines/`. The full procedure is
[Add a capability provider vendor](docs/how-to/add-provider-vendor.md).

## Data and deployment notes

- PostgreSQL is the durable source of truth; pgvector supports semantic
  retrieval.
- Redis is coordination infrastructure, not canonical business storage.
- Absurd stores durable jobs in PostgreSQL. The worker must run for queued
  agent, knowledge, memory, deletion, campaign, event, and recording work.
- Provider secrets are organization-scoped and encrypted at rest.
- Uploaded and recorded objects are namespaced by organization and owning
  resource before reaching a storage adapter.
- The Alembic history is one resettable baseline. Apply it only to a new or
  deliberately reset database; this project does not ship historical data
  migrations.

## License

Apache License 2.0. See `LICENSE`.
