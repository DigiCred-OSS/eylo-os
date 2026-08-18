# Run the platform locally

Use Docker for the API, durable worker, PostgreSQL, and Redis. Run the console
and widget with pnpm so frontend changes reload immediately.

## Prepare configuration

```bash
cp server/eylo/common/config/.env.example \
  server/eylo/common/config/.env.docker
openssl rand -hex 32
```

Put the 64-character result in `ENCRYPTION_KEY`. Keep
`server/eylo/common/config/.env.docker` untracked. Do not reuse the disposable
Docker auth secret or DB password for a hosted deployment.

## Start backend services

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  up -d --build
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  ps
```

The API container applies the single Alembic baseline before Gunicorn starts.
The worker starts only after the API is healthy. The development overlay binds
the API to `127.0.0.1:8000`. PostgreSQL and Redis are reachable only by Compose
services; neither publishes a host port.

Check the public health endpoint:

```bash
curl --fail http://127.0.0.1:8000/health
```

## Start the operator console

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://127.0.0.1:5173`.

## Start the widget

```bash
cd widget
pnpm install --frozen-lockfile
pnpm build
cd preact-ui
pnpm dev
```

Open `http://127.0.0.1:5174`.

## Inspect runtime logs

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  logs --since=10m eylo-server worker
```

PostgreSQL checkpoint messages are routine. Investigate constraint errors,
missing relations, task registration errors, provider connection leaks, and
unhandled task exceptions.

## Stop the runtime

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  down
```

This preserves PostgreSQL and Redis volumes. Use the dedicated
[development reset guide](reset-development-database.md) only when discarding
local data is intentional.
