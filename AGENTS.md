# AGENTS.md

Instructions for coding agents working in this repository. `README.md` is the
human-facing product and setup guide; this file is the operational contract for
changing the code safely.

## Start with an end goal and a TODO list

Never begin implementation without a written TODO list.

1. State the end goal and acceptance criteria.
2. Inspect the active checkout and preserve unrelated changes.
3. Split the work into ordered, independently verifiable slices.
4. Mark steps that require user approval, credentials, or destructive state.
5. Execute the smallest slice, prove its real path, then continue.

If `.codegraph/` exists, use `codegraph explore "<question or symbols>"` before
`rg` or manual file traversal when locating behavior or tracing call paths.

For a bug or review finding, do not patch from the report alone. Reproduce it,
localize the failing boundary, establish RCA and impact, check whether the
finding is valid for this product, then plan the fix. Implement only after that
diagnosis is explicit.

## Repository map

- `server/eylo/framework/` — standalone agent loop.
- `server/eylo/modules/` — domain models, schemas, services, repositories, and
  routes.
- `server/eylo/sockets/` — vendor and transport adapters.
- `server/eylo/pipelines/` — orchestration across domains, vendors, and durable
  work.
- `server/eylo/listeners/` — in-process event subscribers.
- `server/eylo/jobs/` — scheduled execution entrypoints.
- `server/eylo/products/` — product-level composition.
- `web/` — React operator console.
- `widget/` — headless TypeScript SDK and Preact UI.
- `cli/` — API-backed operator CLI.

Documentation is organized by reader need under `docs/`: tutorials, how-to,
reference, explanation, and diagrams. Start at `docs/README.md`; treat active
code, the generated OpenAPI document, catalogs, and runtime composition as the
authorities behind it.

## How to add a provider vendor

Use `docs/how-to/add-provider-vendor.md` as the complete checklist.

1. Extend the owning capability catalog with only executable current options.
2. Implement the vendor protocol in `sockets/<capability>/`; keep SDK types,
   credentials, streams, and vendor errors inside the adapter.
3. Add the explicit factory branch. Do not add reflection, directory scanning,
   a fallback vendor, or a default model.
4. Resolve encrypted organization config in the capability module/pipeline,
   then pass an immutable effective config to the socket.
5. Verify with the cheapest bounded real provider operation and close all
   resources on success, failure, timeout, and cancellation.
6. Extend `modules/provider_onboarding/catalog.py`; reuse shared field kinds and
   AWS region options. Add frontend code only when a real interaction cannot be
   represented by the shared schema.
7. If tools depend on the capability, declare organization, Agent-binding, and
   runtime requirements in the system-tool availability registry.
8. Execute the full public path with real types: create → verify → enable → bind
   → publish → run → inspect sinks/events → cancel/disconnect.
9. Update `docs/reference/providers.md`, affected how-to/explanation pages, and
   the provider compatibility projection.

Do not claim a vendor is supported because its enum/catalog entry exists. The
factory, verification, live execution, cleanup, UI projection, and tenant
boundary are part of the same deliverable.

## Architecture rules

These rules are hard boundaries:

1. `sockets/` and `modules/` do not import each other. Put behavior requiring
   both in `pipelines/`.
2. `framework/` has zero `eylo.*` imports. Keep it usable without the platform.
3. Domain policy belongs in module services, not routes, ORM callbacks, vendor
   adapters, or UI components.
4. Sockets receive resolved secrets and vendor-neutral inputs. They do not
   query organization data or decide product policy.
5. Cross-module aggregation belongs in an aggregate controller or pipeline,
   not hidden repository joins that erase ownership boundaries.
6. Configuration that does nothing is a lie. Wire it to runtime behavior or
   mark it with `experimental()` so the generated API contract says it is
   inert.

## Backend invariants

### Transactions and detached work

- Use `start_transaction()` for an owned DB transaction.
- A detached task must open its own transaction and resolve its own ORM rows.
  Never carry a request-scoped session or attached model into it.
- Emit post-commit events only after the authoritative write succeeds.
- Durable effects get one durable task authority. Do not run the same effect
  from both an in-process callback and the worker.
- Budget checks happen before persisted output or an external side effect.
- Indefinite agent waits must release runtime capacity and resume from durable
  state.

### Configuration and capabilities

- Nothing is preconfigured: no default vendor, model, key, tool, or fallback.
- Missing capability configuration raises `NotConfiguredError` with the
  capability and where to configure it.
- Provider configuration is organization-owned, revisioned, and secret values
  remain encrypted outside the adapter invocation.
- The capability plane contains LLM, STT, TTS, realtime, WebRTC, telephony,
  email, storage, memory, embedding, reranking, and sandbox. Integrations are a
  tool surface, not a capability.
- Agent-provider and agent-tool relations are explicit. Do not infer access
  merely because an organization configured a provider or installed a vendor.

### Domain contracts

- Organizations have members. There is no RBAC, role, admin, or permission
  hierarchy.
- `AgentKind` is either conversational or background and is immutable.
- Draft agents are unusable. Runtime work resolves a published agent revision.
- Background agents cannot join swarms, chain attachments, target another
  organization, or target themselves. Runtime handoffs are disabled for them.
- The platform and framework have distinct `ToolKind` enums. Translate them at
  the pipeline boundary; do not collapse their casing or ownership.
- Model registration is explicit through `register_models()`. Import order can
  be functional, not cosmetic.
- For SQLAlchemy boolean filters, use `.is_(False)` or the established explicit
  expression. Never replace an expression with Python `not`.

### Knowledge and memory

- A knowledgebase owns its chunks. Every read, write, delete, and reindex is
  scoped by organization and knowledgebase identity.
- Scope identifiers come from authenticated/domain context, never model output.
- Grants own read/write authority. A missing filter must fail closed and never
  widen a query.
- Ingestion persists the product job before spawning durable work. Absurd is
  the sole execution authority, and idempotent retries replace the same source's
  chunks rather than merging unrelated stores.
- OCR and content sniffing are not implicit ingestion behavior. Deterministic
  extraction failures are visible.
- Memory ownership is typed: agent, contact, or conversation. Embedding config
  ID and revision determine index validity; reindex after an embedding change.

### Voice, calls, and files

- The primary agent's voice configuration is fixed for the conversation,
  including after swarm handoffs.
- Platform voice policy is independent of vendor-native feature support.
- Recording is the primary path; redaction and policy controls run
  asynchronously after the call. Secondary policy failure must not interrupt
  the live product flow.
- Live flow may hold raw data. Canonical post-call storage is redacted when the
  configured policy requires it.
- Browser, WebSocket, WebRTC, realtime-provider, and telephony sessions are
  children of the user session; each owns and closes its provider resources.
- Storage keys are built by the platform below an operator-provided root or
  bucket. Namespace every object by organization and owning resource. Never
  accept a caller-supplied final path.
- Deletion follows ownership. Deleting a call cannot delete its campaign or
  contacts; provider-side deletion remains the organization's responsibility.

## Frontend, widget, and CLI rules

### Operator console

- Use the public API contract in `web/src/api/generated/`; regenerate it from a
  running server after schema changes.
- Put domain state and API coordination in feature stores/services. Keep local
  interaction state in components and shareable list/detail state in the URL.
- MobX stores hydrate canonical entities by ID. Use aggregate APIs when a screen
  needs a purpose-built cross-module projection.
- Follow the existing Base UI/shadcn composition and neutral design tokens.
  Color is reserved for danger; enum values are badges; dates are human
  readable.
- Lists use the shared search/filter/order/table pattern. Detail opens in a
  drawer. New and edit share a categorized, resumable form.
- Long values wrap; pages must not require horizontal scrolling at supported
  widths.

### Widget

- The SDK owns transport and reactive state; the Preact package owns visual
  composition.
- Do not introduce hidden organization/contact defaults outside the explicit
  local development settings.
- Provider events drive the voice state machine. Do not invent a second UI-only
  call state.
- File upload is shown only when the selected agent permits conversation files.
  The conversation ID is the conversation knowledgebase scope; users do not
  choose a destination.
- Close media tracks, streams, provider connections, timers, and tasks on every
  normal, timeout, cancellation, and abrupt-disconnect path.

### CLI

- The live OpenAPI contract is authoritative for API actions.
- CLI commands call public APIs or application services; they do not bypass
  invariants with direct DB writes.
- Preserve human-readable output and `--json` for automation.

## Alembic and schema changes

This repository carries one resettable Alembic baseline:

- `server/alembic/versions/eylo0001_initial_schema.py`
- `down_revision = None`
- No historical or data migrations.

When models change, rebuild the baseline for a new database. Validate it on a
disposable database with this sequence:

1. `alembic upgrade head`
2. `alembic check`
3. `alembic downgrade base`
4. `alembic upgrade head`

Never downgrade, drop, truncate, or reset an operator database. Resolve and
name the disposable database explicitly before destructive commands.

## Verification policy

The repository intentionally ships no test suite. Tests and probes are working
tools: create them when needed, run them, record the evidence, then remove them
before committing.

For every behavior claim:

1. Trace untrusted source to transport/domain transforms.
2. Inspect the real schema, model fields, constructors, and dependency wiring.
3. Execute the exact changed branch with real types where possible.
4. Observe durable sinks, worker/provider effects, and public projections.
5. Record what was not exercised.

A nearby unit or mock proof cannot replace an end-to-end product-boundary proof
when that path is runnable.

Required local checks for affected surfaces:

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

An app import probe needs at least `ENV`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_NAME`, `AUTH_SECRET_KEY`, a 64-hex-character `ENCRYPTION_KEY`,
`AUTH_ALGORITHM`, `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`, `REDIS_HOST`,
`REDIS_PASSWORD`, and `HOSTING_MODE`.

Do not run broad `ruff --fix`. Side-effect imports register models, events, and
durable tasks; automatic removal can break runtime composition. Read every
proposed lint change.

## Documentation and docstrings

- Keep docs in the Diátaxis home matching their purpose; do not mix tutorials,
  procedures, reference tables, and architecture rationale in one page.
- Update module/pipeline/provider catalogs and diagrams when their source
  authority changes.
- Every non-empty first-party Python module needs a concise responsibility
  docstring. Empty package markers may remain empty.
- Function/class docs explain invariants, side effects, ownership, transaction
  behavior, idempotency, cancellation, or surprising results. Do not repeat a
  clear signature.
- Registered system-tool function docstrings are sent to the LLM. Treat edits
  to them as runtime contract changes and preserve tool-selection, input,
  outcome, and refusal guidance.
- Remove speculative `TODO` essays, Markdown section banners, and generated
  Args/Returns prose that merely restates types. Backlog belongs in a plan or
  issue.
- Follow `docs/reference/source-documentation.md` and validate Markdown links
  plus Mermaid syntax before completion.

## Git, safety, and publication

- Preserve unrelated worktree changes.
- Use `rg` for text and file searches when CodeGraph is not applicable.
- Use `apply_patch` for intentional source edits.
- Avoid broad or unresolved destructive paths. Prefer explicit disposable
  targets and recoverable operations.
- Do not add GitHub Actions, GitLab CI, or any hosted CI/CD. Local pre-commit
  and pre-push hooks own reusable gates.
- Do not commit credentials, database dumps, generated runtime output, caches,
  or temporary probes.
- Do not open a pull request unless the user explicitly requests one.
