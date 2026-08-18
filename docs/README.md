# Eylo documentation

This documentation follows the [Diátaxis](https://diataxis.fr/) structure. Each
page has one job, so setup instructions, task recipes, factual contracts, and
architecture rationale do not compete for attention.

| Need | Documentation type | Start here |
| --- | --- | --- |
| Learn the platform by doing | Tutorial | [Run your first Agent](tutorials/first-agent.md) |
| Complete a specific task | How-to guide | [How-to guides](how-to/README.md) |
| Look up an exact contract | Reference | [Reference](reference/README.md) |
| Understand why the system works this way | Explanation | [Explanation](explanation/README.md) |

## Recommended paths

### Platform operator

1. Read the root [README](../README.md).
2. Complete [Run your first Agent](tutorials/first-agent.md).
3. Use the [operator how-to guides](how-to/README.md) for providers, knowledge,
   memory, voice, integrations, campaigns, and runtime operations.
4. Use the running OpenAPI document at `/docs` for exact HTTP request and
   response schemas.

### Provider author

1. Read [Provider architecture](explanation/provider-architecture.md).
2. Follow [Add a capability provider](how-to/add-provider-vendor.md).
3. Check the [provider reference](reference/providers.md) for current vendors,
   catalogs, factories, and configuration ownership.

### Widget integrator

1. Read the [Widget SDK reference](reference/widget-sdk.md) for the current
   session, lifecycle, service, store, event, Knowledge, integration, and voice
   contracts.
2. Follow [Use the Widget SDK from Preact](how-to/use-widget-sdk.md), which is
   reduced from the running Preact implementation.
3. Use the server-issued invitation/session flow; never let browser input
   choose organization or contact authority.

### Platform maintainer

1. Read [Platform architecture](explanation/architecture.md).
2. Use the [module catalog](reference/modules.md), [pipeline catalog](reference/pipelines.md),
   and [runtime-surface reference](reference/runtime-surfaces.md).
3. Inspect the [architecture diagrams](diagrams/architecture.md) and
   [data-flow diagrams](diagrams/data-flows.md).
4. Follow [source documentation rules](reference/source-documentation.md) when
   changing docstrings or comments.

## Authority and freshness

The active source tree is authoritative. Documentation describes the current
open-source implementation; it does not turn a planned feature into a runtime
contract.

- API paths and boundary schemas: running OpenAPI document.
- Persistence shape: SQLAlchemy models plus the single Alembic baseline.
- Provider availability and form fields: backend catalogs and factories.
- Curated integration tools: the in-process curated registry.
- Runtime composition: `eylo.app`, `eylo.agent_run_worker`, and pipeline wiring.
- Frontend behavior: the console and widget stores, services, routes, and state
  machines.

When code changes one of these contracts, update the closest reference and any
affected how-to or explanation page in the same change.
