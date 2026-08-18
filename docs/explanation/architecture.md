# Platform architecture

Eylo separates product ownership, provider protocols, and Agent execution so an
organization can bring its own infrastructure without making vendor SDKs the
domain model.

## The central boundary

Domain modules know what an Agent, conversation, memory, call, or campaign
means. Sockets know how an external provider speaks. Pipelines know how to
combine the two for one use case.

This creates two enforced dependency rules:

- `modules/` and `sockets/` do not import one another;
- `framework/` imports no `eylo.*` platform package.

The separation is practical. Changing an STT SDK should stay in the socket and
its pipeline wiring. Changing interruption policy should stay in the platform
voice domain/pipeline. Changing the Agent loop should not require loading the
platform's ORM.

## Write ownership and read projections

Each module owns its writes and invariants. Cross-module list/detail screens may
use aggregate controllers or query projections shaped for the UI. That does not
transfer write ownership or justify direct mutation of another module's table.

This is why the console can receive an efficient conversation aggregate while
message, participant, Agent, contact, and voice records retain separate owners.

## Revisioned definitions

Agents, tools, templates, schedules, campaigns, MCP servers, and provider
configs distinguish editable intent from runtime authority. Draft/config
changes create a new version; running work pins a published or current verified
revision.

Pinned revisions make historical conversations explainable and prevent an
operator edit from changing work already underway.

## Durable execution

The request transaction persists product intent first. Absurd then owns the
attempt, retry, wait, and cancellation. A worker reloads exact organization and
revision authority rather than carrying an ORM object or request transaction
into detached work.

This provides durable Agent waits without occupying compute and lets ingestion,
memory, deletion, campaigns, event delivery, and recording uploads share one
DB-backed execution model.

## Live and durable event paths

Ephemeral Pyventus events update live transports and record lightweight
observations. Durable events retain organization-visible facts and coordinate
consumers that require retries and receipts. The two mechanisms are explicit;
neither silently upgrades the guarantee of the other.

## Frontend boundaries

The operator console treats the API as authority, MobX stores as the client
domain/cache, URLs as shareable navigation state, and components as local
interaction state. The widget SDK owns transport/state; Preact owns rendering.

See [architecture diagrams](../diagrams/architecture.md) for context,
dependency, and deployment views.
