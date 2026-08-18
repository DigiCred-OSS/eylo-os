# Deploy with Docker

Use the shared Compose file with the production overlay. The production model
requires explicit secrets and public origins, keeps PostgreSQL and Redis off
the host network, and binds the API to host loopback by default.

## Prepare the production environment

Create the ignored deployment file:

```bash
cp server/eylo/common/config/.env.example \
  server/eylo/common/config/.env.production.docker
```

Set strong, unique values for `DB_PASSWORD`, `REDIS_PASSWORD`,
`AUTH_SECRET_KEY`, and `ENCRYPTION_KEY`. Set the real `API_BASE_URL`,
`OAUTH_CALLBACK_URL`, `FRONTEND_URL`, `WIDGET_URL`, and exact `CORS_ORIGINS`.
Do not copy values from a development installation.

`EYLO_API_BIND_ADDRESS` and `EYLO_API_PORT` control the host API binding. The
default is `127.0.0.1:8000`, suitable for a reverse proxy on the same host. Set
a broader bind address only when the deployment network and firewall require
it.

## Validate the resolved model

The `--env-file` option supplies values for Compose interpolation. The
production overlay also passes the same file to the API and worker containers.

```bash
docker compose \
  --env-file server/eylo/common/config/.env.production.docker \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.prod.yml \
  config --quiet
```

Validation fails when a required production value is missing or empty.

## Start the backend

```bash
docker compose \
  --env-file server/eylo/common/config/.env.production.docker \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.prod.yml \
  up -d --build
```

Publish the console and widget through the deployment's normal static hosting
and TLS boundary. The Compose model intentionally does not publish PostgreSQL
or Redis ports. Do not add temporary host mappings to administer them; use
`docker compose exec postgres-17 ...` or `docker compose exec redis-7 ...`
through the same production file pair.
