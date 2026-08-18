# Add a capability provider vendor

This guide adds a vendor to one of Eylo's provider capabilities: LLM, STT, TTS,
realtime, WebRTC, telephony, email, storage, embedding, reranking, memory, or
sandbox. Curated integrations use a different contract; see
[Install and grant curated integrations](integrations.md).

## End state

A complete provider addition has one vendor-neutral contract, one isolated
adapter, deterministic operator configuration, real verification, runtime
resolution, and a generated console form. A catalog entry without executable
runtime behavior is incomplete.

## 1. Locate the capability seam

Use the existing sibling vendor as the template for file placement, not for
credential assumptions.

| Concern | Typical owner |
| --- | --- |
| Vendor identifier, models, voices, regions, field choices | capability catalog under `eylo/modules/*_configs/` or `eylo/common/contracts/` |
| Encrypted config lifecycle and revisions | `eylo/modules/provider_configs/` plus the capability config module |
| Vendor protocol and SDK types | `eylo/sockets/<capability>/` |
| Config resolution, verification, cross-layer runtime | `eylo/pipelines/<capability>/` |
| Operator form projection | `eylo/modules/provider_onboarding/catalog.py` |
| Console rendering | schema-driven `web/src/features/providers/` |

`modules/` and `sockets/` must not import one another. Anything needing both
belongs in `pipelines/`.

## 2. Extend the vendor catalog

Add the stable vendor identifier to the owning enum or catalog. Add only values
the adapter can honor now:

- model or voice choices;
- supported languages and formats;
- required region or endpoint choices;
- credential field names;
- configuration constraints.

Do not add a default model, bundled credential, or fallback vendor. A field
that is saved but ignored must be removed or explicitly marked experimental in
the generated contract.

## 3. Implement the socket adapter

Implement the existing capability protocol in `eylo/sockets/<capability>/`.
The adapter receives resolved secrets and vendor-neutral input. It may own:

- SDK/client construction;
- vendor request and stream translation;
- vendor response normalization;
- provider-specific cancellation and connection cleanup;
- provider error classification.

It must not query organization data, open platform transactions, choose product
policy, or import a domain module. Keep vendor SDK objects inside this boundary.

## 4. Register the factory branch

Add the vendor to the capability factory. Fail explicitly when required secrets
or region values are absent. Never fall back to another provider.

For voice adapters, normalize events through the existing STT, TTS, or realtime
event contract. Platform interruption, silence, recording, duration, and call
policy remain pipeline concerns even when a provider has native equivalents.

## 5. Wire config resolution and verification

The capability module owns create/list/get/update/delete semantics. The
pipeline resolves an organization-scoped, enabled, verified config revision and
constructs the socket adapter.

Verification must exercise the cheapest real provider action that proves the
credential and selected resource are usable. Bound it with a timeout and close
every client, stream, task, and media resource on success, failure, timeout,
and cancellation.

## 6. Add the onboarding projection

Add the vendor's fields to `provider_onboarding/catalog.py`. Reuse shared field
kinds and AWS region options where applicable. Secret fields must be typed as
secrets; operator-editable endpoints must pass the platform egress policy.

The console reads this catalog. Do not add a vendor-specific React form unless
the existing schema cannot represent a real interaction. If a new field kind is
necessary, extend the backend schema and the shared field renderer together.

## 7. Connect Agent and tool availability

If the capability exposes system tools, ensure availability is computed from
the Agent's explicit mapping and a ready provider configuration. Organization
configuration alone never grants an Agent access.

## 8. Prove the full path

Run, at minimum:

1. create the config through the public API or console;
2. verify it against the real vendor;
3. enable and bind it to an Agent draft;
4. publish the Agent;
5. execute the exact capability path;
6. inspect durable output, normalized events, and UI projection;
7. cancel or disconnect mid-operation and confirm cleanup;
8. confirm another organization receives `404`, not resource disclosure.

Run touched-file Ruff checks plus the relevant console/widget build. Record any
vendor behavior not proven live; a recorded transport is not live coverage.

## 9. Update documentation

Update the provider reference, capability-specific explanation, and any model,
voice, or region choices exposed to operators. Include the vendor's supported
features and deliberate gaps; do not imply the vendor implements Eylo's
platform-owned policy.
