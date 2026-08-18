#!/usr/bin/env python3
"""Verify the sole Alembic baseline against an explicit disposable database."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import asyncpg

from eylo.common.config import Environment, settings

SERVER_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_ROOT = SERVER_ROOT / "alembic" / "versions"
DISPOSABLE_DATABASE_PREFIX = "eylo_oss_migration_"
LOCAL_DATABASE_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    """Observable migration state used to compare both upgrades."""

    revision: str | None
    app_tables: int
    public_enums: int
    absurd_version: str | None
    durable_queue_exists: bool


def require_disposable_database() -> None:
    """Refuse destructive migration commands outside a named local scratch DB."""
    if settings.ENV is not Environment.LOCAL:
        raise RuntimeError("Migration verification requires ENV=local.")
    if settings.DB_HOST not in LOCAL_DATABASE_HOSTS:
        raise RuntimeError("Migration verification requires a local DB host.")
    if not settings.DB_NAME.startswith(DISPOSABLE_DATABASE_PREFIX):
        raise RuntimeError(
            "Migration verification DB_NAME must start with "
            f"{DISPOSABLE_DATABASE_PREFIX!r}."
        )


def require_single_baseline() -> None:
    """Require exactly one resettable migration rooted at eylo0001."""
    migrations = sorted(
        path
        for path in VERSIONS_ROOT.glob("*.py")
        if path.name != "__init__.py"
    )
    expected = VERSIONS_ROOT / "eylo0001_initial_schema.py"
    if migrations != [expected]:
        names = ", ".join(path.name for path in migrations) or "<none>"
        raise RuntimeError(f"Expected only {expected.name}; found {names}.")


def run_alembic(*arguments: str) -> None:
    """Run one Alembic phase in a fresh process to isolate migration globals."""
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVER_ROOT,
        check=True,
    )


async def connect() -> asyncpg.Connection:
    """Connect without rendering credentials into logs or command arguments."""
    return await asyncpg.connect(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
    )


async def snapshot() -> DatabaseSnapshot:
    """Read revision, app schema, and durable-runtime state from PostgreSQL."""
    connection = await connect()
    try:
        revision = await connection.fetchval(
            "SELECT version_num FROM alembic_version LIMIT 1"
        )
        app_tables = await connection.fetchval(
            """
            SELECT count(*)
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename <> 'alembic_version'
            """
        )
        public_enums = await connection.fetchval(
            """
            SELECT count(*)
            FROM pg_type AS type_record
            JOIN pg_namespace AS namespace
              ON namespace.oid = type_record.typnamespace
            WHERE type_record.typtype = 'e'
              AND namespace.nspname = 'public'
            """
        )
        absurd_exists = await connection.fetchval(
            "SELECT to_regnamespace('absurd') IS NOT NULL"
        )
        absurd_version = None
        durable_queue_exists = False
        if absurd_exists:
            absurd_version = await connection.fetchval(
                "SELECT absurd.get_schema_version()"
            )
            durable_queue_exists = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM absurd.queues
                    WHERE queue_name = 'eylo-agent-runs-v1'
                )
                """
            )
        return DatabaseSnapshot(
            revision=revision,
            app_tables=app_tables,
            public_enums=public_enums,
            absurd_version=absurd_version,
            durable_queue_exists=durable_queue_exists,
        )
    finally:
        await connection.close()


def validate_upgrade(state: DatabaseSnapshot) -> None:
    """Require the complete app and pinned durable-runtime baseline."""
    if state.revision != "eylo0001":
        raise RuntimeError(f"Unexpected Alembic revision: {state.revision!r}.")
    if state.app_tables < 1 or state.public_enums < 1:
        raise RuntimeError("Upgraded baseline is missing app tables or enums.")
    if state.absurd_version != "0.4.0" or not state.durable_queue_exists:
        raise RuntimeError("Upgraded baseline is missing pinned Absurd state.")


def validate_downgrade(state: DatabaseSnapshot) -> None:
    """Require the resettable baseline to remove all product-owned DB objects."""
    expected = DatabaseSnapshot(None, 0, 0, None, False)
    if state != expected:
        raise RuntimeError(f"Downgrade left product-owned database state: {state!r}.")


def main() -> int:
    """Run upgrade, drift check, downgrade, and byte-for-byte state re-upgrade."""
    require_disposable_database()
    require_single_baseline()

    run_alembic("upgrade", "head")
    run_alembic("check")
    first_upgrade = asyncio.run(snapshot())
    validate_upgrade(first_upgrade)

    run_alembic("downgrade", "base")
    validate_downgrade(asyncio.run(snapshot()))

    run_alembic("upgrade", "head")
    second_upgrade = asyncio.run(snapshot())
    validate_upgrade(second_upgrade)
    if second_upgrade != first_upgrade:
        raise RuntimeError(
            "Migration state changed across the downgrade/re-upgrade round trip."
        )

    print(
        "MIGRATION-ROUND-TRIP-OK "
        f"revision={second_upgrade.revision} "
        f"tables={second_upgrade.app_tables} "
        f"enums={second_upgrade.public_enums} "
        f"absurd={second_upgrade.absurd_version} "
        "queue=eylo-agent-runs-v1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
