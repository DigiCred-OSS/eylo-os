# Configuration reference

Deployment environment configures infrastructure and trusted egress roots.
Organizations configure vendors through authenticated APIs. These are separate
authority planes.

## Required deployment values

| Variable | Meaning |
| --- | --- |
| `ENV` | `local` or `prod` |
| `HOSTING_MODE` | `local` or `docker`; controls environment-file selection |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | PostgreSQL connection |
| `AUTH_SECRET_KEY`, `AUTH_ALGORITHM`, `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | bearer-token signing and lifetime |
| `ENCRYPTION_KEY` | exactly 64 hexadecimal characters used for provider-secret encryption |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` | Redis coordination connection |

`DATABASE_URL` and `REDIS_URL` are derived by `EyloSettings`.

The Docker deployment has one shared service definition and two explicit
overlays. `docker-compose.dev.yml` supplies disposable local values;
`docker-compose.prod.yml` requires deployment values from the ignored
`.env.production.docker` file. PostgreSQL and Redis are internal-only in both
models. Compose publishes only the API port, bound to loopback unless the
production operator explicitly sets `EYLO_API_BIND_ADDRESS`.

## Public origins and callbacks

| Variable | Meaning |
| --- | --- |
| `API_BASE_URL` | public API root used in generated links and callbacks |
| `OAUTH_CALLBACK_URL` | curated integration OAuth callback; normally `<api>/api/oauth/callback` |
| `FRONTEND_URL` | member console origin |
| `WIDGET_URL` | contact widget origin |
| `SERVER_DOMAIN` | public telephony webhook host where needed |
| `CORS_ORIGINS` | exact JSON array of browser origins |

## Trusted deployment controls

| Variable | Meaning |
| --- | --- |
| `STORAGE_FILESYSTEM_ROOT` | host/mounted root below which the platform builds organization/resource namespaces |
| `EMBEDDING_BASE_URL_ALLOWLIST` | exact operator-approved custom embedding endpoints |
| `RERANKING_BASE_URL_ALLOWLIST` | exact operator-approved custom reranking endpoints |
| `TWILIO_API_BASE_URL` | trusted Twilio-compatible egress override; organizations cannot set it |

## Local widget identity

`WIDGET_DEVELOPMENT_ORGANIZATION_ID` and
`WIDGET_DEVELOPMENT_CONTACT_ID` must be configured together and are accepted
only for `ENV=local`. They exist to run the standalone widget against one real
contact without adding a production identity default.

## Feature controls

The current settings include worker, streaming, prompt-caching, realtime voice,
recording, fire-and-forget task, compound widget interface, and mock-mode
switches. A feature flag controls platform behavior; it does not configure a
vendor or grant an Agent a capability.

## Organization provider config

LLM, voice, WebRTC, telephony, email, storage, embedding, reranking, memory, and
sandbox credentials belong in provider config rows. They must not be added as
process-wide vendor keys. This preserves organization ownership and allows
multiple explicit configurations per capability.
