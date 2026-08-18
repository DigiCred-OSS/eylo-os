# Provider architecture

Eylo is a bring-your-own-provider platform. A provider configuration supplies
organization authority; a socket supplies protocol behavior; a pipeline
connects that adapter to product work.

## Why provider config is separate from adapters

An adapter should be reusable for many organizations and configurations. It
must not know which organization owns a credential or how that secret is
stored. The provider-config domain therefore owns:

- organization and capability identity;
- encrypted secrets;
- public non-secret settings;
- current revision and verification metadata;
- enabled/deleted/readiness state.

The pipeline resolves that aggregate to an immutable in-memory effective
config. Only then does a factory construct the socket adapter.

## Why verification is a separate action

Saving proves only that the request fits the schema. Verification proves that
the selected vendor credential/resource works. Separating them lets operators
save incomplete work, rotate secrets without pretending they are valid, and
see the exact readiness state.

Verification is capability-specific because “valid” means different things:
list a cheap model/resource, open and close a bounded stream, fetch ICE
credentials, inspect storage access, or execute another vendor-defined probe.

## Catalog-driven UI

The server projects capabilities, vendors, fields, options, conditions, and
secret/reference types through one onboarding catalog. The console renders the
same form system for every capability.

This avoids frontend/vendor drift. A vendor-specific component is justified
only when a real interaction cannot be represented by the shared schema.

## Platform features versus vendor capabilities

Provider-native features are facts about an adapter. Platform voice, memory,
knowledge, tool, and execution policy remain Eylo contracts. A vendor may offer
native VAD, interruption, caching, or reranking; the pipeline decides how that
maps into platform behavior.

Unsupported native features are visible as compatibility data. They do not
silently disable platform policy or make inert configuration appear effective.

## Integrations are different

Curated integrations expose Agent tools for an external application. They are
not interchangeable runtime capabilities such as LLM or storage. Their
registry, installations, connections, origin-pinned tool context, and mutation
receipts therefore live in the integrations boundary rather than provider
configs.
