# Reset a disposable development database

This procedure destroys the Docker development database and all local runtime
rows. Never use it against an operator database.

## Confirm the target

Check that the Compose project is `eylo` and that the target is the local
`postgres-17` service produced by the base and development Compose files.
Export any provider configuration backup you intend to preserve before
continuing.

## Remove local volumes

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  down -v
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  up -d --build
```

The API recreates the schema by applying `eylo0001`.

## Verify the baseline

From `server/`, against the explicitly selected disposable database:

```bash
uv run alembic upgrade head
uv run alembic check
uv run alembic downgrade base
uv run alembic upgrade head
```

The repository carries no historical data migrations. A model change requires
regenerating the single baseline for a fresh database, then repeating this
round trip.
